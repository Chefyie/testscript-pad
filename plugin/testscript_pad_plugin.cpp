//=============================================================================
// Testscript-Pad server plugin (Orange Box / TF2, 32-bit)
//
// Adds console commands that Testscript-Pad runs over RCON to ask the game
// about its entities. Every output line starts with TSP_ and its fields are
// separated by tabs, so the editor can read them back:
//
//   tsp_version                  TSP_VERSION <n>
//   tsp_pick [pitch yaw]         TSP_PICK line for the entity under the
//                                crosshair, then TSP_HIT <x y z> (the point
//                                looked at). Angles default to the player's.
//   tsp_ents [text]              TSP_ENT line per live entity (only names /
//                                classes containing text), then TSP_END <count>
//   tsp_find <hammerid|name>     TSP_ENT lines for that hammerid, targetname
//                                or classname, then TSP_END <count>
//
// TSP_PICK / TSP_ENT fields:
//   classname, targetname, hammerid, origin, angles, model, parentname
//=============================================================================

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "interface.h"
#include "eiface.h"
#include "engine/iserverplugin.h"
#include "engine/IEngineTrace.h"
#include "gametrace.h"
#include "bspflags.h"
#include "iserverunknown.h"
#include "engine/ICollideable.h"
#include "toolframework/itoolentity.h"
#include "game/server/iplayerinfo.h"
#include "tier1/tier1.h"
#include "tier1/convar.h"
#include "tier1/strtools.h"

// memdbgon must be the last include
#include "tier0/memdbgon.h"

#define TSP_PLUGIN_VERSION "1"

static IVEngineServer *engine = NULL;
static IEngineTrace *enginetrace = NULL;
static IServerTools *servertools = NULL;
static IServerGameClients *gameclients = NULL;
static IPlayerInfoManager *playerinfomanager = NULL;

//-----------------------------------------------------------------------------
// Entity helpers
//-----------------------------------------------------------------------------
static void GetKV( void *ent, const char *key, char *out, int len )
{
	out[0] = '\0';
	if ( !servertools->GetKeyValue( ent, key, out, len ) )
		out[0] = '\0';
	// keep the output one line per entity and tab separated; drop values that
	// aren't plain text (brush entities return binary data for "model")
	for ( char *c = out; *c; ++c )
	{
		unsigned char u = (unsigned char)*c;
		if ( u == '\t' || u == '\n' || u == '\r' )
			*c = ' ';
		else if ( u < 32 || u > 126 )
		{
			out[0] = '\0';
			return;
		}
	}
}

// CBaseEntity's first base class is IServerEntity -> IServerUnknown, so the
// entity pointer the server tools hand out is also an IServerUnknown pointer.
static void GetPlacement( void *ent, char *org, int orgLen, char *ang, int angLen )
{
	ICollideable *col = ent ? ( (IServerUnknown *)ent )->GetCollideable() : NULL;
	if ( !col )
		return;
	if ( !org[0] )
	{
		const Vector &o = col->GetCollisionOrigin();
		Q_snprintf( org, orgLen, "%g %g %g", o.x, o.y, o.z );
	}
	if ( !ang[0] )
	{
		const QAngle &a = col->GetCollisionAngles();
		Q_snprintf( ang, angLen, "%g %g %g", a.x, a.y, a.z );
	}
}

static void PrintEntity( const char *tag, void *ent )
{
	char cls[128], name[128], hid[32], org[96], ang[96], model[256], parent[128];
	GetKV( ent, "classname", cls, sizeof( cls ) );
	GetKV( ent, "targetname", name, sizeof( name ) );
	GetKV( ent, "hammerid", hid, sizeof( hid ) );
	GetKV( ent, "origin", org, sizeof( org ) );
	GetKV( ent, "angles", ang, sizeof( ang ) );
	GetKV( ent, "model", model, sizeof( model ) );
	GetKV( ent, "parentname", parent, sizeof( parent ) );
	GetPlacement( ent, org, sizeof( org ), ang, sizeof( ang ) );
	if ( !strcmp( hid, "0" ) )
		hid[0] = '\0';		// spawned by a script / the game, not from the map
	Msg( "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", tag, cls, name, hid, org, ang, model, parent );
}

static bool ContainsNoCase( const char *haystack, const char *needle )
{
	return !needle[0] || Q_stristr( haystack, needle ) != NULL;
}

//-----------------------------------------------------------------------------
// Commands
//-----------------------------------------------------------------------------
CON_COMMAND( tsp_version, "Testscript-Pad plugin version" )
{
	Msg( "TSP_VERSION\t%s\n", TSP_PLUGIN_VERSION );
}

// Trace filter that ignores the player doing the looking
class CTraceFilterSkipOne : public ITraceFilter
{
public:
	CTraceFilterSkipOne( IHandleEntity *skip ) : m_pSkip( skip ) {}
	virtual bool ShouldHitEntity( IHandleEntity *pEntity, int contentsMask ) { return pEntity != m_pSkip; }
	virtual TraceType_t GetTraceType() const { return TRACE_EVERYTHING; }
private:
	IHandleEntity *m_pSkip;
};

static bool IsWorld( void *ent )
{
	char cls[64];
	GetKV( ent, "classname", cls, sizeof( cls ) );
	return !strcmp( cls, "worldspawn" );
}

// Slab test: does the ray start + dir * t (0 <= t <= maxDist) pass through the box?
static bool RayHitsBox( const Vector &start, const Vector &dir, float maxDist,
						const Vector &mins, const Vector &maxs, float *pDist )
{
	float tmin = 0.0f, tmax = maxDist;
	for ( int axis = 0; axis < 3; ++axis )
	{
		if ( fabsf( dir[axis] ) < 1e-6f )
		{
			if ( start[axis] < mins[axis] || start[axis] > maxs[axis] )
				return false;
			continue;
		}
		float t1 = ( mins[axis] - start[axis] ) / dir[axis];
		float t2 = ( maxs[axis] - start[axis] ) / dir[axis];
		if ( t1 > t2 ) { float tmp = t1; t1 = t2; t2 = tmp; }
		if ( t1 > tmin ) tmin = t1;
		if ( t2 < tmax ) tmax = t2;
		if ( tmin > tmax )
			return false;
	}
	*pDist = tmin;
	return true;
}

// The first real (non-bot) player: on a listen server, that's you.
static edict_t *LocalPlayer( IPlayerInfo **ppInfo )
{
	for ( int i = 1; i <= 32; ++i )
	{
		edict_t *ed = engine->PEntityOfEntIndex( i );
		if ( !ed || ed->IsFree() || !ed->GetUnknown() )
			continue;
		IPlayerInfo *info = playerinfomanager->GetPlayerInfo( ed );
		if ( info && info->IsConnected() && !info->IsFakeClient() )
		{
			*ppInfo = info;
			return ed;
		}
	}
	return NULL;
}

CON_COMMAND( tsp_pick, "Testscript-Pad: describe the entity under your crosshair [pitch yaw]" )
{
	IPlayerInfo *info = NULL;
	edict_t *player = ( gameclients && playerinfomanager ) ? LocalPlayer( &info ) : NULL;
	if ( !player )
	{
		Msg( "TSP_ERROR\tno player in the game yet (load a map and join a team first)\n" );
		return;
	}
	Vector eye;
	gameclients->ClientEarPosition( player, &eye );
	QAngle view;
	if ( args.ArgC() >= 3 )
		view.Init( (float)atof( args.Arg( 1 ) ), (float)atof( args.Arg( 2 ) ), 0.0f );
	else
		view = info->GetLastUserCommand().viewangles;

	const float rad = 3.14159265358979f / 180.0f;
	Vector forward( cosf( view.x * rad ) * cosf( view.y * rad ),
					cosf( view.x * rad ) * sinf( view.y * rad ),
					-sinf( view.x * rad ) );
	Vector end = eye + forward * 16384.0f;

	Ray_t ray;
	ray.Init( eye, end );
	CTraceFilterSkipOne filter( player->GetUnknown() );
	trace_t tr;
	enginetrace->TraceRay( ray, MASK_SHOT | CONTENTS_GRATE, &filter, &tr );

	// The trace only hits solid things. Intel, triggers, logic entities and props
	// without collision are found by checking which entity boxes the line of
	// sight passes through before it hits something solid.
	float bestDist = tr.fraction * 16384.0f;
	void *best = ( tr.fraction < 1.0f ) ? (void *)tr.m_pEnt : NULL;
	char cls[64];
	if ( best && IsWorld( best ) )
		bestDist += 1.0f;		// anything right in front of a wall wins over the wall
	// Trigger volumes (capture zones, door triggers...) usually surround the
	// thing you're looking at, so they only win when nothing else is there.
	void *bestTrigger = NULL;
	float bestTriggerDist = bestDist;
	IHandleEntity *self = player->GetUnknown();
	for ( void *ent = servertools->FirstEntity(); ent; ent = servertools->NextEntity( ent ) )
	{
		if ( ent == best || (IHandleEntity *)(IServerUnknown *)ent == self )
			continue;
		ICollideable *col = ( (IServerUnknown *)ent )->GetCollideable();
		if ( !col )
			continue;
		Vector mins, maxs;
		col->WorldSpaceSurroundingBounds( &mins, &maxs );
		mins -= Vector( 4, 4, 4 );		// point entities have no size
		maxs += Vector( 4, 4, 4 );
		if ( eye.x >= mins.x && eye.x <= maxs.x && eye.y >= mins.y && eye.y <= maxs.y &&
			 eye.z >= mins.z && eye.z <= maxs.z )
			continue;					// big volumes we're standing in (spawn rooms, map-wide triggers)
		float dist;
		if ( !RayHitsBox( eye, forward, bestDist, mins, maxs, &dist ) )
			continue;
		GetKV( ent, "classname", cls, sizeof( cls ) );
		if ( !strcmp( cls, "worldspawn" ) || !strncmp( cls, "tf_", 3 ) || !strcmp( cls, "player" ) )
			continue;					// world, teams, gamerules, other players' bookkeeping
		// by class, not by FSOLID_TRIGGER: the intel and pickups are triggers too,
		// but they're the objects you're looking at, not volumes around them
		bool trigger = !strncmp( cls, "trigger_", 8 ) || !strcmp( cls, "func_capturezone" ) ||
					   !strcmp( cls, "func_respawnroom" ) || !strcmp( cls, "func_nobuild" ) ||
					   !strcmp( cls, "func_regenerate" ) || !strcmp( cls, "func_respawnroomvisualizer" );
		if ( trigger )
		{
			if ( dist < bestTriggerDist )
			{
				bestTrigger = ent;
				bestTriggerDist = dist;
			}
		}
		else if ( dist < bestDist )
		{
			best = ent;
			bestDist = dist;
		}
	}
	if ( bestTrigger && ( !best || IsWorld( best ) ) )
		best = bestTrigger;

	if ( best )
		PrintEntity( "TSP_PICK", best );
	else
		Msg( "TSP_PICK\tnone\n" );
	if ( tr.fraction < 1.0f )
		Msg( "TSP_HIT\t%g %g %g\n", tr.endpos.x, tr.endpos.y, tr.endpos.z );
}

CON_COMMAND( tsp_ents, "Testscript-Pad: list live entities [only names/classes containing text]" )
{
	const char *filter = args.ArgC() > 1 ? args.Arg( 1 ) : "";
	int count = 0;
	char cls[128], name[128];
	for ( void *ent = servertools->FirstEntity(); ent; ent = servertools->NextEntity( ent ) )
	{
		if ( filter[0] )
		{
			GetKV( ent, "classname", cls, sizeof( cls ) );
			GetKV( ent, "targetname", name, sizeof( name ) );
			if ( !ContainsNoCase( cls, filter ) && !ContainsNoCase( name, filter ) )
				continue;
		}
		PrintEntity( "TSP_ENT", ent );
		++count;
	}
	Msg( "TSP_END\t%d\n", count );
}

CON_COMMAND( tsp_find, "Testscript-Pad: find entities by hammerid, targetname or classname" )
{
	if ( args.ArgC() < 2 )
	{
		Msg( "TSP_ERROR\tusage: tsp_find <hammerid|name>\n" );
		return;
	}
	const char *what = args.Arg( 1 );
	int count = 0;
	char *endp = NULL;
	long hammerid = strtol( what, &endp, 10 );
	if ( endp && *endp == '\0' && hammerid > 0 )
	{
		void *ent = servertools->FindEntityByHammerID( (int)hammerid );
		if ( ent )
		{
			PrintEntity( "TSP_ENT", ent );
			++count;
		}
	}
	else
	{
		char cls[128], name[128];
		for ( void *ent = servertools->FirstEntity(); ent; ent = servertools->NextEntity( ent ) )
		{
			GetKV( ent, "classname", cls, sizeof( cls ) );
			GetKV( ent, "targetname", name, sizeof( name ) );
			if ( !Q_stricmp( cls, what ) || !Q_stricmp( name, what ) )
			{
				PrintEntity( "TSP_ENT", ent );
				++count;
			}
		}
	}
	Msg( "TSP_END\t%d\n", count );
}

//-----------------------------------------------------------------------------
// Plugin
//-----------------------------------------------------------------------------
class CTestscriptPadPlugin : public IServerPluginCallbacks
{
public:
	virtual bool Load( CreateInterfaceFn interfaceFactory, CreateInterfaceFn gameServerFactory )
	{
		ConnectTier1Libraries( &interfaceFactory, 1 );
		engine = (IVEngineServer *)interfaceFactory( INTERFACEVERSION_VENGINESERVER, NULL );
		enginetrace = (IEngineTrace *)interfaceFactory( INTERFACEVERSION_ENGINETRACE_SERVER, NULL );
		servertools = (IServerTools *)gameServerFactory( VSERVERTOOLS_INTERFACE_VERSION, NULL );
		if ( !engine || !enginetrace || !servertools || !g_pCVar )
		{
			Warning( "Testscript-Pad plugin: the game is missing an interface it needs, not loading\n" );
			return false;
		}
		gameclients = (IServerGameClients *)gameServerFactory( INTERFACEVERSION_SERVERGAMECLIENTS, NULL );
		playerinfomanager = (IPlayerInfoManager *)gameServerFactory( INTERFACEVERSION_PLAYERINFOMANAGER, NULL );
		ConVar_Register( 0 );
		// The engine never really unloads a plugin DLL, and tier1 hands its command
		// list over only once per DLL load, so after plugin_unload + plugin_load the
		// commands have to be registered again by hand.
		ConCommand *commands[] = { &tsp_version_command, &tsp_pick_command, &tsp_ents_command, &tsp_find_command };
		for ( int i = 0; i < (int)( sizeof( commands ) / sizeof( commands[0] ) ); ++i )
			if ( !g_pCVar->FindCommandBase( commands[i]->GetName() ) )
				g_pCVar->RegisterConCommand( commands[i] );
		Msg( "Testscript-Pad plugin %s loaded%s\n", TSP_PLUGIN_VERSION,
			 ( gameclients && playerinfomanager ) ? "" : " (tsp_pick unavailable: player interfaces missing)" );
		return true;
	}

	virtual void Unload()
	{
		ConVar_Unregister();
		DisconnectTier1Libraries();
	}

	virtual const char *GetPluginDescription() { return "Testscript-Pad " TSP_PLUGIN_VERSION; }

	virtual void Pause() {}
	virtual void UnPause() {}
	virtual void LevelInit( char const *pMapName ) {}
	virtual void ServerActivate( edict_t *pEdictList, int edictCount, int clientMax ) {}
	virtual void GameFrame( bool simulating ) {}
	virtual void LevelShutdown() {}
	virtual void ClientActive( edict_t *pEntity ) {}
	virtual void ClientDisconnect( edict_t *pEntity ) {}
	virtual void ClientPutInServer( edict_t *pEntity, char const *playername ) {}
	virtual void SetCommandClient( int index ) {}
	virtual void ClientSettingsChanged( edict_t *pEdict ) {}
	virtual PLUGIN_RESULT ClientConnect( bool *bAllowConnect, edict_t *pEntity, const char *pszName,
										 const char *pszAddress, char *reject, int maxrejectlen ) { return PLUGIN_CONTINUE; }
	virtual PLUGIN_RESULT ClientCommand( edict_t *pEntity, const CCommand &args ) { return PLUGIN_CONTINUE; }
	virtual PLUGIN_RESULT NetworkIDValidated( const char *pszUserName, const char *pszNetworkID ) { return PLUGIN_CONTINUE; }
	virtual void OnQueryCvarValueFinished( QueryCvarCookie_t iCookie, edict_t *pPlayerEntity, EQueryCvarValueStatus eStatus,
										   const char *pCvarName, const char *pCvarValue ) {}
};

static CTestscriptPadPlugin g_TestscriptPadPlugin;
EXPOSE_SINGLE_INTERFACE_GLOBALVAR( CTestscriptPadPlugin, IServerPluginCallbacks,
								   INTERFACEVERSION_ISERVERPLUGINCALLBACKS, g_TestscriptPadPlugin );
