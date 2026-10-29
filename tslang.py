"""Language support for Orange Box (Source 2007 / TF2) testscripts.

A testscript is a plain text file of console commands that the game runs from
top to bottom:

  * commands are separated by newlines or ';'  (';' ends a command even when a
    quote is still open, which is why scripts can leave quotes unclosed:
    ent_fire x addoutput"origin 0 0 11;)
  * a '"' starts a string that ends at the next '"', ';' or end of line
  * '//' starts a comment
  * a line starting with '///' ends the script
  * Test_Wait <seconds> pauses the script so queued ent_fire events can run

This module has no GUI code: vocabulary, lexer, highlighter, completion
context and the script checker (linter) all live here.
"""

import re
import string
from collections import Counter


def _table(spec):
    out = {}
    for raw in spec.strip().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        name, _, desc = raw.partition('|')
        out[name.strip()] = desc.strip()
    return out


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

COMMANDS = _table("""
alias | alias <name> "<command>" - makes <name> run <command>. Scripts use one-letter aliases for repeated spawns, e.g. alias a"give math_counter;
give | give <classname> - spawns an entity at your crosshair (needs sv_cheats)
ent_create | ent_create <classname> [key value ...] - spawns an entity at your crosshair, optionally with keyvalues
ent_fire | ent_fire <target> <input> [parameter] [delay] - queues an input on every entity whose targetname or classname matches (* wildcards allowed)
ent_keyvalue | ent_keyvalue <hammerid|name> <key> <value> [<key> <value> ...] - sets keyvalues/outputs on an entity immediately
ent_setname | ent_setname <name> - sets the targetname of the entity under your crosshair (or the one you just spawned)
ent_remove | ent_remove [name] - removes the entity under your crosshair, or by name
ent_remove_all | ent_remove_all <name|classname> - removes every matching entity
ent_teleport | ent_teleport <name> - moves an entity to your crosshair
ent_rotate | ent_rotate <name> <degrees> - rotates an entity around its yaw
ent_text | ent_text [name] - shows debug text overlay for an entity
ent_bbox | ent_bbox [name] - shows an entity's bounding box
ent_absbox | ent_absbox [name] - shows an entity's absolute bounding box
ent_messages | ent_messages [name] - prints the entity I/O an entity sends/receives
ent_dump | ent_dump <name> - prints an entity's keyvalues to the console
ent_info | ent_info <classname> - lists the inputs/outputs of an entity class
ent_pivot | ent_pivot [name] - shows an entity's pivot
ent_cancelpendingentfires | ent_cancelpendingentfires - cancels every queued ent_fire event
prop_dynamic_create | prop_dynamic_create <model> - spawns a prop_dynamic (model path without models/ and .mdl)
prop_physics_create | prop_physics_create <model> - spawns a physics prop
noclip | noclip - toggles noclip flying
god | god - toggles god mode
buddha | buddha - toggles buddha mode
notarget | notarget - toggles notarget
setpos | setpos <x> <y> <z> - moves you to a world position
setpos_exact | setpos_exact <x> <y> <z> - moves you to an exact world position
setang | setang <pitch> <yaw> [roll] - sets your view angles
setang_exact | setang_exact <pitch> <yaw> <roll> - sets exact view angles
getpos | getpos - prints your position and angles as setpos/setang commands
impulse | impulse <n> - runs an impulse command
kill | kill - kills yourself
explode | explode - kills yourself with an explosion
echo | echo <text> - prints text to the console
say | say <text> - sends a chat message
say_team | say_team <text> - sends a team chat message
exec | exec <file> - runs a .cfg file
wait | wait [frames] - waits frames (console command, not Test_Wait)
play | play <sound> - plays a sound locally
playgamesound | playgamesound <sound> - plays a game sound
stopsound | stopsound - stops all sounds
bot | bot [-team red|blue] [-class name] - adds a bot
bot_kick | bot_kick <name|all> - kicks a bot
changelevel | changelevel <map> - changes map
map | map <map> - loads a map
bind | bind <key> <command> - binds a key
unbind | unbind <key> - unbinds a key
incrementvar | incrementvar <cvar> <min> <max> <step> - steps a cvar
toggle | toggle <cvar> [values] - toggles a cvar
joinclass | joinclass <class> - switches class
join_class | join_class <class> - switches class
jointeam | jointeam <red|blue|spectator|auto> - switches team
changeclass | changeclass - opens the class menu
changeteam | changeteam - opens the team menu
use | use <weapon classname> - switches to that weapon
lastinv | lastinv - switches to the last weapon
slot1 | slot1 - selects weapon slot 1
slot2 | slot2 - selects weapon slot 2
slot3 | slot3 - selects weapon slot 3
slot4 | slot4 - selects weapon slot 4
slot5 | slot5 - selects weapon slot 5
fov | fov <degrees> - sets field of view
firstperson | firstperson - first person camera
thirdperson | thirdperson - third person camera
addcond | addcond <n> - adds a TF2 condition to yourself (cheats)
removecond | removecond <n> - removes a TF2 condition
hurtme | hurtme <amount> - damages yourself
voicemenu | voicemenu <menu> <item> - plays a voice command
restart | restart - restarts the map
disconnect | disconnect - leaves the server
Test_Wait | Test_Wait <seconds> - pauses the testscript. Put it after spawns/renames so queued ent_fire events finish before the next lines run
Test_StartLoop | Test_StartLoop <label> - marks the start of a testscript loop
Test_Loop | Test_Loop <label> - jumps back to a Test_StartLoop label
Test_LoopCount | Test_LoopCount <label> <count> - jumps back to a label a set number of times
Test_LoopForNumSeconds | Test_LoopForNumSeconds <label> <seconds> - loops back to a label for a number of seconds
Test_WaitForCheckPoint | Test_WaitForCheckPoint <name> - waits for a checkpoint
Test_SendKey | Test_SendKey <key> - simulates a key press
Test_RandomChance | Test_RandomChance <percent> <command> - runs a command with a random chance
Test_StartScript | Test_StartScript <file> - runs another testscript (path relative to the testscripts folder)
Test_CreateEntity | Test_CreateEntity <classname> - spawns an entity at your crosshair
picker | picker - toggles picking the entity under your crosshair (used with !picker)
""")

CVAR_PREFIXES = (
    'mp_', 'tf_', 'sv_', 'r_', 'cl_', 'fog_', 'hud_', 'bot_', 'mat_', 'host_',
    'net_', 'snd_', 'ai_', 'phys_', 'tv_', 'voice_', 'm_', 'fps_', 'cc_',
    'vgui_', 'demo_', 'developer', 'cam_', 'viewmodel_', 'sk_', 'nb_', 'spec_',
)

COMMON_CVARS = [
    'mp_restartround', 'mp_restartgame', 'mp_winlimit', 'mp_timelimit',
    'mp_maxrounds', 'mp_autoteambalance', 'mp_teams_unbalance_limit',
    'mp_allowspectators', 'mp_scrambleteams', 'mp_tournament', 'mp_respawnwavetime',
    'mp_disable_respawn_times', 'mp_friendlyfire', 'mp_forcecamera',
    'tf_flag_caps_per_round', 'tf_spy_cloak_regen_rate', 'tf_playergib',
    'sv_cheats', 'sv_gravity', 'sv_airaccelerate', 'host_timescale',
    'r_screenoverlay', 'fog_override', 'fog_enable', 'fog_start', 'fog_end',
    'fog_color', 'fog_maxdensity', 'hud_fastswitch', 'hud_classautokill',
    'cl_drawhud', 'mat_fullbright',
]

INPUTS = _table("""
kill | Removes the entity from the world
killhierarchy | Removes the entity and everything parented to it
addoutput | addoutput "<key> <value>" sets a keyvalue, or "<Output> target,input,param,delay,times" adds an output
enable | Enables the entity
disable | Disables the entity
toggle | Toggles enabled/disabled (or on/off)
trigger | Fires the logic_relay / trigger outputs
use | Same as a player pressing +use on it
setteam | setteam <0-3> - 0 none, 1 spectator, 2 RED, 3 BLU
setparent | setparent <name> - attaches this entity to another so it moves with it
setparentattachment | setparentattachment <attachment> - attaches to a named model attachment
clearparent | Removes the parent
fireuser1 | Fires OnUser1
fireuser2 | Fires OnUser2
fireuser3 | Fires OnUser3
fireuser4 | Fires OnUser4
display | game_text / game_text_tf: shows the message
add | math_counter: adds the parameter to the value
subtract | math_counter: subtracts the parameter from the value
multiply | math_counter: multiplies the value
divide | math_counter: divides the value
setvalue | math_counter / logic_compare: sets the value (fires outputs)
setvaluenofire | math_counter: sets the value without firing outputs
getvalue | math_counter: fires OnGetValue with the current value
sethitmin | math_counter: sets the minimum
sethitmax | math_counter: sets the maximum
invalue | logic_case: compares the parameter against Case01..Case16
pickrandom | logic_case: fires a random OnCase output
pickrandomshuffle | logic_case: fires a random OnCase without repeating until all were used
compare | logic_compare: compares value against compare value
setcomparevalue | logic_compare: sets the value to compare against
setvaluecompare | logic_compare: sets the value and compares
testactivator | filter_*: tests the activator, firing OnPass or OnFail
roundwin | game_round_win: ends the round
settime | team_round_timer: sets the remaining time (seconds)
addtime | team_round_timer: adds seconds
removetime | team_round_timer: removes seconds
setmaxtime | team_round_timer: sets the maximum time
pause | team_round_timer: pauses
resume | team_round_timer: resumes
restart | team_round_timer: restarts
showinhud | team_round_timer: 1 shows / 0 hides the timer on the HUD
setsetuptime | team_round_timer: sets the setup time
autocountdown | team_round_timer: enables/disables the announcer countdown
start | func_train / func_tracktrain: starts moving
stop | func_train / func_tracktrain: stops
startforward | func_tracktrain: moves forward
startbackward | func_tracktrain: moves backward
reverse | func_tracktrain: reverses direction
setspeed | Sets the speed
setspeeddir | func_tracktrain: sets speed with direction
setspeedreal | func_tracktrain: sets speed in units per second
teleporttopathtrack | func_tracktrain: teleports to a path_track
open | func_door: opens
close | func_door: closes
lock | Locks
unlock | Unlocks
skin | skin <n> - changes the model skin (0 neutral/red, 1 red/blu ...)
color | color "<r> <g> <b>" - changes render color
alpha | alpha <0-255> - changes render alpha
setanimation | prop_dynamic: plays an animation
setdefaultanimation | prop_dynamic: sets the idle animation
setplaybackrate | prop_dynamic: animation speed
enablecollision | prop_dynamic: becomes solid
disablecollision | prop_dynamic: becomes non-solid
enablemotion | prop_physics: enables physics motion
disablemotion | prop_physics: freezes physics motion
break | Breaks a breakable
sethealth | Sets health
addhealth | Adds health
removehealth | Removes health
explode | env_explosion: explodes
startspark | env_spark: starts sparking
stopspark | env_spark: stops sparking
sparkonce | env_spark: sparks once
showsprite | env_sprite: shows
hidesprite | env_sprite: hides
playsound | ambient_generic: plays the sound
stopsound | ambient_generic: stops the sound
volume | ambient_generic: sets the volume
pitch | ambient_generic: sets the pitch
command | point_clientcommand / point_servercommand: runs a console command (clientcommand runs on the !activator)
countplayersinzone | game_zone_player: fires OnPlayerInZone / OnPlayerOutZone for every player
forcerespawn | game_forcerespawn: respawns every player
forceteamrespawn | game_forcerespawn: respawns one team
setowner | team_control_point: sets the owning team (0 neutral, 2 RED, 3 BLU)
setlocked | team_control_point: locks/unlocks
setunlocktime | team_control_point: unlocks after seconds
hidemodel | team_control_point: hides the hologram model
showmodel | team_control_point: shows the hologram model
roundspawn | team_control_point_master: re-initialises the control points
setcaplayout | team_control_point_master: sets the HUD cap layout
cancelpending | logic_relay: cancels its queued outputs
refiretime | logic_timer: sets the refire interval
firetimer | logic_timer: fires OnTimer now
resettimer | logic_timer: restarts the timer
lowerrandombound | logic_timer: random lower bound
upperrandombound | logic_timer: random upper bound
setblueteamrespawnwavetime | tf_gamerules: BLU respawn wave time
setredteamrespawnwavetime | tf_gamerules: RED respawn wave time
setblueteamgoalstring | tf_gamerules: BLU goal text on the HUD
setredteamgoalstring | tf_gamerules: RED goal text on the HUD
setblueteamrole | tf_gamerules: BLU role
setredteamrole | tf_gamerules: RED role
playvo | tf_gamerules: plays a voice-over to everyone
playvored | tf_gamerules: plays a voice-over to RED
playvoblue | tf_gamerules: plays a voice-over to BLU
turnon | Turns on (lights, rotating)
turnoff | Turns off
ignite | Sets on fire
settext | Sets text
""")

OUTPUTS = _table("""
OnTrigger | logic_relay / trigger: fired when triggered
OnPass | filter_*: the activator passed the filter
OnFail | filter_*: the activator failed the filter
OnStartTouch | trigger_*: something entered
OnEndTouch | trigger_*: something left
OnStartTouchAll | trigger_*: first thing entered
OnEndTouchAll | trigger_*: last thing left
OnTouching | trigger_*: TouchTest result - something is touching
OnNotTouching | trigger_*: TouchTest result - nothing touching
OnCase01 | logic_case: value matched Case01
OnCase02 | logic_case: value matched Case02
OnCase03 | logic_case: value matched Case03
OnCase04 | logic_case: value matched Case04
OnCase05 | logic_case: value matched Case05
OnCase06 | logic_case: value matched Case06
OnCase07 | logic_case: value matched Case07
OnCase08 | logic_case: value matched Case08
OnCase09 | logic_case: value matched Case09
OnCase10 | logic_case: value matched Case10
OnCase11 | logic_case: value matched Case11
OnCase12 | logic_case: value matched Case12
OnCase13 | logic_case: value matched Case13
OnCase14 | logic_case: value matched Case14
OnCase15 | logic_case: value matched Case15
OnCase16 | logic_case: value matched Case16
OnDefault | logic_case: no case matched
OnEqualTo | logic_compare: value == compare value
OnNotEqualTo | logic_compare: value != compare value
OnLessThan | logic_compare: value < compare value
OnGreaterThan | logic_compare: value > compare value
OutValue | math_counter: fired with the new value whenever it changes
OnGetValue | math_counter: fired by the GetValue input
OnHitMin | math_counter: reached min
OnHitMax | math_counter: reached max
OnChangedFromMin | math_counter: left min
OnChangedFromMax | math_counter: left max
OnFinished | team_round_timer: time ran out
OnRoundStart | team_round_timer: a round started (use it to reset your gamemode each round)
OnSetupStart | team_round_timer: setup started
OnSetupFinished | team_round_timer: setup finished
On1SecRemain | team_round_timer: 1 second left
On2SecRemain | team_round_timer: 2 seconds left
On3SecRemain | team_round_timer: 3 seconds left
On4SecRemain | team_round_timer: 4 seconds left
On5SecRemain | team_round_timer: 5 seconds left
On10SecRemain | team_round_timer: 10 seconds left
On30SecRemain | team_round_timer: 30 seconds left
On1MinRemain | team_round_timer: 1 minute left
On2MinRemain | team_round_timer: 2 minutes left
On3MinRemain | team_round_timer: 3 minutes left
On4MinRemain | team_round_timer: 4 minutes left
On5MinRemain | team_round_timer: 5 minutes left
OnTimer | logic_timer: fired every refire interval
OnTimerHigh | logic_timer: oscillator high
OnTimerLow | logic_timer: oscillator low
OnUser1 | Fired by FireUser1
OnUser2 | Fired by FireUser2
OnUser3 | Fired by FireUser3
OnUser4 | Fired by FireUser4
OnCapture | item_teamflag / func_capturezone: the flag was captured
OnReturn | item_teamflag: the flag returned
OnPickup | item_teamflag: the flag was picked up
OnPickupTeam1 | item_teamflag: picked up by RED
OnPickupTeam2 | item_teamflag: picked up by BLU
OnDrop | item_teamflag: the flag was dropped
OnTouchSameTeam | item_teamflag: touched by its own team
OnCapTeam1 | trigger_capture_area: RED captured
OnCapTeam2 | trigger_capture_area: BLU captured
OnCapReset | trigger_capture_area: capture progress reset
OnStartCap | trigger_capture_area: capping started
OnBreakCap | trigger_capture_area: capping was blocked/broken
OnNumCappersChanged | trigger_capture_area: number of cappers changed
OnOwnerChangedToTeam1 | team_control_point: now owned by RED
OnOwnerChangedToTeam2 | team_control_point: now owned by BLU
OnPlayerInZone | game_zone_player: fired per player inside (after CountPlayersInZone)
OnPlayerOutZone | game_zone_player: fired per player outside (after CountPlayersInZone)
OnPlayerTouch | item_*: a player picked it up
OnSpawn | Fired when spawned
OnBreak | Fired when broken
OnHealthChanged | Health changed
OnTakeDamage | Took damage
OnOpen | func_door: started opening
OnClose | func_door: started closing
OnFullyOpen | func_door: fully open
OnFullyClosed | func_door: fully closed
OnPressed | func_button: pressed
OnDamaged | func_button: damaged
OnMapSpawn | logic_auto: map spawned
OnArrivedAtDestinationNode | path_track: train arrived
OnTeleport | path_track: train teleported here
OnAnimationBegun | prop_dynamic: animation started
OnAnimationDone | prop_dynamic: animation finished
""")

KEYVALUES = _table("""
targetname | The name other entities use to target this one
classname | The entity class. Scripts rename it so later 'ent_fire <class>' commands don't hit it, or set it to 'player' so it survives round restarts
hammerid | A number you pick so 'ent_keyvalue <id>' can find the entity (needs Test_Wait after setting)
origin | "x y z" world position
angles | "pitch yaw roll"
model | Model path (models/....mdl) or "." for invisible brush entities
spawnflags | Bit flags (triggers: 1 = clients)
solid | 0 not solid, 2 bounding box (use 2 on spawned triggers)
mins | "x y z" lower corner of the bounding box
maxs | "x y z" upper corner of the bounding box
parentname | Parent entity name
message | Text for game_text / game_text_tf
color | "r g b" color (game_text text color)
color2 | "r g b" game_text effect color
rendercolor | "r g b" model tint
renderamt | Alpha 0-255
rendermode | Render mode
renderfx | Render effect
skin | Model skin
modelscale | Model scale
disableshadows | 1 disables shadows
x | game_text: horizontal position 0-1, -1 centers
y | game_text: vertical position 0-1, -1 centers
channel | game_text: text channel 1-6 (same channel replaces text)
holdtime | game_text: seconds on screen
fadein | game_text: fade in seconds
fadeout | game_text: fade out seconds
fxtime | game_text: effect time
effect | game_text: 0 fade, 1 flicker, 2 scan out
icon | game_text_tf: icon (e.g. voice_player, ico_notify_flag_moving)
background | game_text_tf: 0 none, 2 RED, 3 BLU
display_to_team | game_text_tf: 0 everyone, 2 RED, 3 BLU
min | math_counter: minimum
max | math_counter: maximum
startvalue | math_counter: initial value
Case01 | logic_case: value to match
Case02 | logic_case: value to match
Case03 | logic_case: value to match
Case04 | logic_case: value to match
Case05 | logic_case: value to match
Case06 | logic_case: value to match
Case07 | logic_case: value to match
Case08 | logic_case: value to match
Case09 | logic_case: value to match
Case10 | logic_case: value to match
Case11 | logic_case: value to match
Case12 | logic_case: value to match
Case13 | logic_case: value to match
Case14 | logic_case: value to match
Case15 | logic_case: value to match
Case16 | logic_case: value to match
filtername | filter_activator_name: name to match
filterclass | filter_activator_class: class to match
Negated | filter: 1 inverts the result
TeamNum | Team number (2 RED, 3 BLU)
target | Next path_track / target entity
speed | Movement speed
dmg | func_train: crush damage
damage | trigger_hurt: damage per second (negative heals)
damagetype | Damage type flags
wait | Delay before re-triggering
controlpoint | func_capturezone: associated control point
GameType | item_teamflag: game type (0 CTF)
StartDisabled | 1 starts disabled
force_map_reset | game_round_win: 1 resets the map when the round ends
team | Team number
iMagnitude | env_explosion: damage/size
iRadiusOverride | env_explosion: radius
refiretime | logic_timer: seconds between OnTimer
UseRandomTime | logic_timer: 1 uses random time
LowerRandomBound | logic_timer: random min
UpperRandomBound | logic_timer: random max
health | Health
timer_length | team_round_timer: length in seconds
setup_length | team_round_timer: setup length
max_length | team_round_timer: maximum length
start_paused | team_round_timer: 1 starts paused
show_in_hud | team_round_timer: 1 shows on HUD
show_time_remaining | team_round_timer: show remaining time
auto_countdown | team_round_timer: announcer countdown
reset_time | team_round_timer: reset on round start
team_model_0 | team_control_point: neutral model
team_model_2 | team_control_point: RED model
team_model_3 | team_control_point: BLU model
team_icon_0 | team_control_point: neutral HUD icon
team_icon_2 | team_control_point: RED HUD icon
team_icon_3 | team_control_point: BLU HUD icon
point_printname | team_control_point: name on the HUD
point_default_owner | team_control_point: starting owner
point_index | team_control_point: index
area_time_to_cap | trigger_capture_area: seconds to capture
area_cap_point | trigger_capture_area: control point name
team_cancap_2 | trigger_capture_area: RED can cap
team_cancap_3 | trigger_capture_area: BLU can cap
ReturnTime | item_teamflag: seconds before a dropped flag returns
radius | Radius
volume | ambient_generic: volume
gravity | Gravity
friction | Friction
pushdir | trigger_push: direction
""")

ENTITIES = _table("""
math_counter | Stores a number; Add/Subtract/SetValue inputs, OutValue/OnHitMax outputs
logic_case | Compares a value to Case01-16 and fires OnCaseXX (InValue, PickRandom)
logic_relay | Fires OnTrigger when triggered
logic_compare | Compares two values (OnEqualTo/OnLessThan/OnGreaterThan)
logic_timer | Fires OnTimer every RefireTime seconds
logic_auto | Fires outputs on map spawn
logic_branch | Boolean branch
filter_activator_tfteam | Passes if the activator is on its team (SetTeam)
filter_activator_name | Passes if the activator's name matches filtername
filter_activator_class | Passes if the activator's class matches filterclass
filter_multi | Combines filters
filter_damage_type | Passes on a damage type
team_round_timer | Round timer (OnRoundStart, OnFinished, SetTime, ShowInHUD)
game_round_win | Ends the round for its team (RoundWin)
game_text | Shows HUD text (Display)
game_text_tf | Shows a TF2 notification with an icon (Display)
game_zone_player | CountPlayersInZone fires OnPlayerInZone/OutZone per player
game_forcerespawn | Respawns players (ForceRespawn)
trigger_multiple | Brush trigger (OnStartTouch/OnEndTouch); needs solid 2, mins/maxs, spawnflags 1
trigger_once | Trigger that fires once
trigger_hurt | Hurts (or heals with negative damage) players inside
trigger_push | Pushes things inside
trigger_teleport | Teleports things inside
trigger_brush | Brush that receives the player's input
trigger_capture_area | Control point capture zone
func_capturezone | Flag capture zone (SetTeam, solid 2, mins/maxs)
func_nobuild | Engineers can't build inside
func_respawnroom | Respawn room
func_respawnroomvisualizer | Respawn room barrier for the enemy team
func_regenerate | Resupply locker zone
func_train | Moving brush that follows path_track (Start/Stop)
func_tracktrain | Train that follows path_track
func_door | Door
func_wall | Solid wall (solid 2, mins/maxs)
func_brush | Toggleable brush
func_button | Button
func_rotating | Rotating brush
func_movelinear | Linear mover
func_illusionary | Non-solid brush
path_track | Node for trains (target = next node, OnPass)
path_corner | Node for func_train
item_teamflag | CTF intelligence / flag (SetTeam, OnCapture, OnReturn)
item_ammopack_small | Small ammo pack
item_ammopack_medium | Medium ammo pack
item_ammopack_full | Full ammo pack
item_healthkit_small | Small health kit
item_healthkit_medium | Medium health kit
item_healthkit_full | Full health kit
info_player_teamspawn | Player spawn point (SetTeam)
info_player_start | Map start point
infodecal | Decal
info_target | Invisible target point
info_particle_system | Particle effect
info_teleport_destination | Teleport destination
info_observer_point | Spectator camera point
point_clientcommand | Runs a console command on the activator (Command)
point_servercommand | Runs a server console command (Command)
point_viewcontrol | Camera
point_template | Spawns templates
point_spotlight | Spotlight
point_teleport | Teleports a target
point_push | Pushes things around it
point_hurt | Hurts things around it
env_spark | Sparks (StartSpark/StopSpark)
env_explosion | Explosion (Explode, iMagnitude)
env_sprite | Sprite
env_shake | Screen shake
env_fade | Screen fade
env_beam | Beam
env_laser | Laser
env_fire | Fire
env_smokestack | Smoke
env_lightglow | Light glow
env_screenoverlay | Screen overlay
ambient_generic | Sound (PlaySound/StopSound)
multisource | Fires OnTrigger when used (scripts use it as a relay that survives restarts)
prop_dynamic | Animated/model prop
prop_physics | Physics prop
prop_physics_multiplayer | Multiplayer physics prop
prop_physics_override | Physics prop override
team_control_point | Control point (SetOwner)
team_control_point_master | Control point master
tf_gamerules | TF2 game rules (respawn times, goal strings)
keyframe_rope | Rope
move_rope | Rope
beam | Beam
light | Light
light_spot | Spot light
light_dynamic | Dynamic light
obj_sentrygun | Sentry gun
obj_dispenser | Dispenser
obj_teleporter | Teleporter
tf_weapon_builder | Engineer/spy builder weapon
player | Players. Entities renamed to classname 'player' are kept on round restart
worldspawn | The world
""")

SPECIAL_TARGETS = ['!activator', '!caller', '!self', '!player', '!picker', '!pvsplayer']

COMMON_MODELS = [
    'props_mining/support_wall001a', 'props_gameplay/cap_point_base',
    'effects/cappoint_hologram', 'props_farm/fence_metal01a',
    'props_spytech/rocket002_top', 'props_trainyard/crane_platform001',
    'props_spytech/work_table001', 'props_mining/track_arc_90degree_128',
    'props_mining/track_arc_90degree_256', 'props_mining/track_straight_128',
    'props_mining/track_straight_256', 'props_mining/track_s_curve_48',
    'props_trainyard/train_sign002', 'props_2fort/roof_metal003',
    'props_farm/wood_framing001c', 'props_vehicles/mining_cart_supplies002',
]

COMMANDS_L = {k.lower(): k for k in COMMANDS}
INPUTS_L = {k.lower(): k for k in INPUTS}
OUTPUTS_L = {k.lower(): k for k in OUTPUTS}
KEYVALUES_L = {k.lower(): k for k in KEYVALUES}
ENTITIES_L = {k.lower(): k for k in ENTITIES}

# Commands whose first argument is a target (name or classname)
TARGET_COMMANDS = {'ent_remove', 'ent_remove_all', 'ent_text', 'ent_bbox', 'ent_absbox',
                   'ent_teleport', 'ent_messages', 'ent_dump', 'ent_pivot', 'ent_rotate'}
MODEL_COMMANDS = {'prop_dynamic_create', 'prop_physics_create'}
SPAWN_COMMANDS = {'give', 'ent_create'}

WORD_CHARS = set(string.ascii_letters + string.digits + '_!*@`^./-?#$')


def is_cvar(name):
    return name.lower().startswith(CVAR_PREFIXES)


def is_output(name):
    n = name.lower()
    if n in OUTPUTS_L or n == 'outvalue':
        return True
    return n.startswith('on') and len(n) > 3 and n not in KEYVALUES_L


def lookup_help(kind, word):
    """Return (canonical, description) for a word, or None."""
    w = word.lower().strip('"; ')
    tables = {
        'command': (COMMANDS_L, COMMANDS), 'testcmd': (COMMANDS_L, COMMANDS),
        'input': (INPUTS_L, INPUTS), 'output': (OUTPUTS_L, OUTPUTS),
        'key': (KEYVALUES_L, KEYVALUES), 'entity': (ENTITIES_L, ENTITIES),
    }
    if kind in tables:
        low, table = tables[kind]
        if w in low:
            return low[w], table[low[w]]
        if kind == 'entity':
            w = w.rstrip('*')
            if w in low:
                return low[w], table[low[w]]
    if kind == 'cvar':
        return word, 'Console variable'
    if kind == 'special':
        return word, {'!activator': 'The entity that started the I/O chain (usually the player)',
                      '!caller': 'The entity that fired this output',
                      '!self': 'This entity',
                      '!player': 'The first player',
                      '!picker': 'The entity under the local player\'s crosshair'}.get(w, 'Special target')
    return None


# --------------------------------------------------------------------------
# Lexer
# --------------------------------------------------------------------------

class Word:
    __slots__ = ('start', 'end', 'text', 'quoted', 'closed', 'qstart')

    def __init__(self, start, end, text, quoted=False, closed=True, qstart=None):
        self.start = start          # first char of the content
        self.end = end              # one past the last char of the content
        self.text = text
        self.quoted = quoted
        self.closed = closed        # quoted words: had a closing '"'
        self.qstart = start if qstart is None else qstart

    def __repr__(self):
        return f'Word({self.text!r})'


class Statement:
    __slots__ = ('words', 'start', 'end', 'sep')

    def __init__(self, words, start, end, sep):
        self.words = words
        self.start = start
        self.end = end
        self.sep = sep              # index of the terminating ';' or None


def lex_line(line):
    """Split one line into statements. Returns (statements, comment_start)."""
    stmts = []
    words = []
    i = 0
    n = len(line)
    stmt_start = 0
    comment = None
    while i < n:
        c = line[i]
        if c == '"':
            j = i + 1
            while j < n and line[j] not in '";':
                j += 1
            closed = j < n and line[j] == '"'
            words.append(Word(i + 1, j, line[i + 1:j], True, closed, i))
            i = j + 1 if closed else j
            continue
        if c in ' \t\r\n':
            i += 1
            continue
        if c == ';':
            if words:
                stmts.append(Statement(words, stmt_start, i, i))
            words = []
            stmt_start = i + 1
            i += 1
            continue
        if line.startswith('//', i):
            comment = i
            break
        j = i
        while j < n and line[j] not in ' \t\r\n;"' and not line.startswith('//', j):
            j += 1
        words.append(Word(i, j, line[i:j]))
        i = j
    if words:
        stmts.append(Statement(words, stmt_start, comment if comment is not None else n, None))
    return stmts, comment


def is_end_marker(line):
    return line.lstrip().startswith('///')


# --------------------------------------------------------------------------
# Highlighter
# --------------------------------------------------------------------------

NUM_RE = re.compile(r'(?<![\w.])[-+]?(?:\d+\.?\d*|\.\d+)(?![\w.])')


def command_tag(cmd, aliases):
    if cmd in aliases:
        return 'alias'
    if cmd in COMMANDS_L:
        return 'testcmd' if cmd.startswith('test_') else 'command'
    if is_cvar(cmd):
        return 'cvar'
    return 'unknown'


def target_tag(text):
    t = text.strip().lower()
    if t.startswith('!'):
        return 'special'
    if t.rstrip('*') in ENTITIES_L:
        return 'entity'
    return 'target'


def _numbers(text, offset, spans):
    for m in NUM_RE.finditer(text):
        spans.append((offset + m.start(), offset + m.end(), 'number'))


def _core(text):
    """(lead, length) of text with surrounding spaces and ';' stripped."""
    stripped = text.lstrip()
    lead = len(text) - len(stripped)
    core = stripped.rstrip(' \t;')
    return lead, len(core), core


def _hl_io(text, offset, spans, aliases, depth):
    """Highlight an output value: target,input,parameter,delay,times."""
    pos = 0
    fields = text.split(',')
    inp = fields[1].strip().lower() if len(fields) > 1 else ''
    for idx, f in enumerate(fields):
        start = offset + pos
        lead, ln, core = _core(f)
        if ln:
            s, e = start + lead, start + lead + ln
            if idx == 0:
                spans.append((s, e, target_tag(core)))
            elif idx == 1:
                spans.append((s, e, 'input'))
            elif idx == 2:
                if inp == 'addoutput':
                    _hl_kv_text(f, start, spans, aliases, depth)
                elif inp == 'command' and depth < 3:
                    _hl_fragment(f, start, aliases, spans, depth + 1)
                else:
                    _numbers(f, start, spans)
            else:
                spans.append((s, e, 'number'))
        pos += len(f) + 1
        if idx < len(fields) - 1:
            spans.append((offset + pos - 1, offset + pos, 'sep'))


def _hl_kv_text(text, offset, spans, aliases, depth):
    """Highlight "key value" or "Output target,input,..." (addoutput parameter)."""
    m = re.match(r'\s*([^\s;]+)', text)
    if not m:
        return
    key = m.group(1)
    ks = offset + m.start(1)
    rest = text[m.end(1):]
    rest_off = offset + m.end(1)
    if is_output(key):
        spans.append((ks, ks + len(key), 'output'))
        lead = len(rest) - len(rest.lstrip())
        _hl_io(rest.lstrip(), rest_off + lead, spans, aliases, depth)
    else:
        spans.append((ks, ks + len(key), 'key'))
        if key.lower() in ('targetname', 'classname'):
            lead, ln, core = _core(rest)
            if ln:
                spans.append((rest_off + lead, rest_off + lead + ln, 'targetdef'))
        else:
            _numbers(rest, rest_off, spans)


def _hl_pairs(words, offset, spans, aliases, depth):
    for i in range(0, len(words), 2):
        key = words[i]
        out = is_output(key.text)
        spans.append((offset + key.start, offset + key.end, 'output' if out else 'key'))
        if i + 1 < len(words):
            val = words[i + 1]
            if out:
                _hl_io(val.text, offset + val.start, spans, aliases, depth)
            elif key.text.lower() in ('targetname', 'classname'):
                spans.append((offset + val.start, offset + val.end, 'targetdef'))
            else:
                _numbers(val.text, offset + val.start, spans)


def _hl_statement(words, text, offset, aliases, spans, depth):
    def tag(w, t):
        if w.end > w.start:
            spans.append((offset + w.start, offset + w.end, t))

    w0 = words[0]
    cmd = w0.text.lower()
    tag(w0, command_tag(cmd, aliases))
    args = words[1:]
    if not args:
        return
    if cmd == 'alias':
        tag(args[0], 'aliasdef')
        for w in args[1:]:
            if depth < 3:
                _hl_fragment(w.text, offset + w.start, aliases, spans, depth + 1)
        return
    if cmd == 'ent_fire':
        tag(args[0], target_tag(args[0].text))
        if len(args) < 2:
            return
        tag(args[1], 'input')
        params = args[2:]
        if not params:
            return
        inp = args[1].text.lower()
        if inp == 'addoutput':
            p = params[0]
            if p.quoted:
                _hl_kv_text(p.text, offset + p.start, spans, aliases, depth)
            else:
                seg = text[p.start:params[-1].end]
                _hl_kv_text(seg, offset + p.start, spans, aliases, depth)
        elif inp == 'command' and depth < 3:
            for p in params:
                _hl_fragment(p.text, offset + p.start, aliases, spans, depth + 1)
        elif inp in ('setparent', 'setparentattachment'):
            tag(params[0], 'target')
        else:
            for p in params:
                _numbers(p.text, offset + p.start, spans)
        return
    if cmd in SPAWN_COMMANDS:
        tag(args[0], 'entity')
        _hl_pairs(args[1:], offset, spans, aliases, depth)
        return
    if cmd == 'ent_keyvalue':
        tag(args[0], 'hammerid' if args[0].text.isdigit() else target_tag(args[0].text))
        _hl_pairs(args[1:], offset, spans, aliases, depth)
        return
    if cmd in MODEL_COMMANDS:
        tag(args[0], 'model')
        return
    if cmd == 'ent_setname':
        tag(args[0], 'targetdef')
        return
    if cmd in TARGET_COMMANDS:
        tag(args[0], target_tag(args[0].text))
        args = args[1:]
    for w in args:
        _numbers(w.text, offset + w.start, spans)


def _hl_fragment(text, offset, aliases, spans, depth):
    stmts, comment = lex_line(text)
    for st in stmts:
        for w in st.words:
            if w.quoted:
                spans.append((offset + w.qstart, offset + w.end + (1 if w.closed else 0), 'string'))
        if st.sep is not None:
            spans.append((offset + st.sep, offset + st.sep + 1, 'sep'))
        _hl_statement(st.words, text, offset, aliases, spans, depth)
    if comment is not None:
        spans.append((offset + comment, offset + len(text), 'comment'))


def highlight_line(line, aliases=frozenset(), dead=False):
    """Return [(start_col, end_col, tag)] for one line."""
    if dead:
        return [(0, len(line), 'dead')] if line else []
    if is_end_marker(line):
        return [(0, len(line), 'endmark')]
    spans = []
    _hl_fragment(line, 0, aliases, spans, 0)
    return spans


def token_at(line, col, aliases=frozenset()):
    """Return (tag, text) of the highlighted token under col."""
    best = None
    for s, e, t in highlight_line(line, aliases):
        if s <= col <= e and t not in ('string', 'sep') and e > s:
            if best is None or (e - s) < (best[1] - best[0]):
                best = (s, e, t)
    if best is None:
        return None
    return best[2], line[best[0]:best[1]]


# --------------------------------------------------------------------------
# Completion context
# --------------------------------------------------------------------------

def current_prefix(line, col):
    i = col
    while i > 0 and line[i - 1] in WORD_CHARS:
        i -= 1
    return i, line[i:col]


def _kv_ctx(inner):
    if not inner.strip() or not re.search(r'\s', inner.lstrip()):
        return 'key'
    key = inner.split()[0]
    if is_output(key):
        rest = inner.lstrip()[len(key):]
        return _io_ctx(rest.lstrip())
    return None


def _io_ctx(inner):
    commas = inner.count(',')
    if commas == 0:
        return 'target'
    if commas == 1:
        return 'input'
    fields = inner.split(',')
    if commas == 2 and fields[1].strip().lower() == 'addoutput':
        return _kv_ctx(fields[2])
    if commas == 2 and fields[1].strip().lower() == 'command':
        return _ctx(fields[2], len(fields[2]), 1)
    return None


def _ctx(head, col, depth):
    head = head[:col]
    if is_end_marker(head):
        return None
    stmts, comment = lex_line(head)
    if comment is not None:
        return None
    if not stmts or stmts[-1].sep is not None:
        return 'command'
    words = stmts[-1].words
    last = words[-1]
    in_quote = last.quoted and not last.closed and last.end == len(head)
    if in_quote:
        before = words[:-1]
    elif head and head[-1] in WORD_CHARS and last.end == len(head):
        before = words[:-1]
    else:
        before = words
    idx = len(before)
    if idx == 0:
        return None if in_quote else 'command'
    cmd = before[0].text.lower()

    if in_quote:
        inner = last.text
        if cmd == 'alias' and idx >= 2 and depth < 3:
            return _ctx(inner, len(inner), depth + 1)
        if cmd == 'ent_fire' and idx >= 3:
            inp = before[2].text.lower()
            if inp == 'addoutput':
                return _kv_ctx(inner)
            if inp == 'command' and depth < 3:
                return _ctx(inner, len(inner), depth + 1)
            return None
        if cmd == 'ent_keyvalue' or cmd in SPAWN_COMMANDS:
            if idx >= 2 and (idx - 2) % 2 == 1:
                if is_output(before[idx - 1].text):
                    return _io_ctx(inner)
                return None
            if idx >= 2:
                return 'key' if not re.search(r'\s', inner) else None
        return None

    if cmd == 'ent_fire':
        if idx == 1:
            return 'target'
        if idx == 2:
            return 'input'
        if idx == 3 and before[2].text.lower() == 'addoutput':
            return 'key'
        if idx == 3 and before[2].text.lower() in ('setparent',):
            return 'target'
        return None
    if cmd in SPAWN_COMMANDS:
        if idx == 1:
            return 'entity'
        return 'key' if (idx - 2) % 2 == 0 else None
    if cmd == 'ent_keyvalue':
        if idx == 1:
            return 'hammerid'
        return 'key' if (idx - 2) % 2 == 0 else None
    if cmd in MODEL_COMMANDS and idx == 1:
        return 'model'
    if cmd in TARGET_COMMANDS and idx == 1:
        return 'target'
    if cmd == 'alias' and idx >= 2:
        return 'command'
    return None


def completion_context(line, col):
    """Return (kind, prefix_start) for the cursor position.

    kind is one of command, target, entity, input, key, hammerid, model or None.
    """
    start, _ = current_prefix(line, col)
    return _ctx(line, col, 0), start


# --------------------------------------------------------------------------
# Analysis / checker
# --------------------------------------------------------------------------

class Diagnostic:
    __slots__ = ('line', 'col', 'end', 'severity', 'message')

    def __init__(self, line, col, end, severity, message):
        self.line, self.col, self.end = line, col, end
        self.severity, self.message = severity, message


class Analysis:
    def __init__(self):
        self.aliases = {}            # name -> (line, body)
        self.alias_uses = Counter()
        self.names = {}              # name -> [(line, kind)]
        self.hammerids = {}          # id -> {'line', 'cls', 'name'}
        self.models = set()
        self.sections = []           # (line, title)
        self.end_line = None
        self.diagnostics = []

    def alias_names(self):
        return frozenset(self.aliases)

    def next_hammerid(self):
        ids = [int(k) for k in self.hammerids if k.isdigit() and int(k) < 100000]
        return max(ids) + 1 if ids else 1

    def add_name(self, name, line, kind):
        name = name.strip().strip('"; ')
        if not name or name.lower() in ENTITIES_L or ' ' in name:
            return
        self.names.setdefault(name, []).append((line, kind))

    def diag(self, line, col, end, severity, message):
        self.diagnostics.append(Diagnostic(line, col, end, severity, message))


RUNTIME_NAME_RE = re.compile(r'addoutput,\s*targetname\s+([^\s,;"]+)', re.I)


def _value(text):
    return text.strip().strip('"').strip(' ;')


class _Checker:
    def __init__(self, text):
        self.a = Analysis()
        self.lines = text.split('\n')
        self.live = set()        # classnames spawned by the script and not renamed yet
        self.pending_ids = set() # hammerids set since the last Test_Wait
        self.tn_defs = {}        # targetname -> first line (script spawned entities)

    def run(self):
        a = self.a
        warned_after_end = False
        for ln, line in enumerate(self.lines, 1):
            if a.end_line is not None:
                if line.strip() and not warned_after_end:
                    a.diag(ln, 0, len(line), 'info', "Text after the '///' end marker is ignored")
                    warned_after_end = True
                continue
            if is_end_marker(line):
                a.end_line = ln
                continue
            stmts, comment = lex_line(line)
            if comment is not None and not stmts:
                title = line[comment:].lstrip('/').strip()
                if title:
                    a.sections.append((ln, title))
            for st in stmts:
                self.statement(st.words, ln, line, 0, None)
            for m in RUNTIME_NAME_RE.finditer(line):
                a.add_name(m.group(1), ln, 'runtime targetname')
        if a.end_line is None and any(l.strip() for l in self.lines):
            last = len(self.lines)
            a.diag(last, 0, len(self.lines[-1]), 'warning',
                   "Script has no '///' end marker - testscripts normally end with a '///' line")
        for name, (ln, body) in a.aliases.items():
            if not a.alias_uses[name]:
                a.diag(ln, 0, len(self.lines[ln - 1]), 'info', f"Alias '{name}' is never used")
        a.diagnostics.sort(key=lambda d: (d.line, d.col))
        return a

    # -- helpers ---------------------------------------------------------
    def span(self, via, w):
        """Columns to underline: the alias call when expanding, else the word."""
        if via is not None:
            return via.start, via.end
        return w.start, w.end

    def define_targetname(self, name, ln, col, end):
        name = _value(name)
        if not name:
            return
        key = name.lower()
        if key in self.tn_defs and self.tn_defs[key] != ln:
            self.a.diag(ln, col, end, 'info',
                        f"Targetname '{name}' is already used by an entity made on line {self.tn_defs[key]}")
        else:
            self.tn_defs.setdefault(key, ln)

    def check_output(self, value, ln, col, end):
        fields = value.split(',')
        if len(fields) > 5:
            self.a.diag(ln, col, end, 'warning',
                        'Output has more than 5 fields (target,input,parameter,delay,times)')

    # -- statements ------------------------------------------------------
    def statement(self, words, ln, line, depth, via):
        a = self.a
        w0 = words[0]
        cmd = w0.text.lower()
        args = words[1:]
        c0, c1 = self.span(via, w0)

        if cmd in a.aliases and cmd != 'alias':
            a.alias_uses[cmd] += 1
            if depth < 4:
                body = a.aliases[cmd][1]
                for st in lex_line(body)[0]:
                    self.statement(st.words, ln, line, depth + 1, via or w0)
            return

        if cmd == 'alias':
            if not args:
                a.diag(ln, c0, c1, 'error', 'alias needs a name')
                return
            name = args[0].text.lower()
            body = ' '.join(w.text for w in args[1:])
            if name in a.aliases:
                a.diag(ln, args[0].start, args[0].end, 'info',
                       f"Alias '{name}' is redefined (first defined on line {a.aliases[name][0]})")
            if name in COMMANDS_L:
                a.diag(ln, args[0].start, args[0].end, 'warning',
                       f"Alias '{name}' hides the '{COMMANDS_L[name]}' command")
            a.aliases[name] = (ln, body)
            return

        if cmd == 'test_wait':
            if not args or not NUM_RE.fullmatch(args[0].text):
                a.diag(ln, c0, c1, 'error', 'Test_Wait needs a number of seconds, e.g. Test_Wait .1')
            self.pending_ids.clear()
            return

        if cmd in SPAWN_COMMANDS:
            if not args:
                a.diag(ln, c0, c1, 'error', f'{cmd} needs a classname')
                return
            cls = args[0].text
            if cls.lower() not in ENTITIES_L:
                s0, s1 = self.span(via, args[0])
                a.diag(ln, s0, s1, 'info', f"'{cls}' is not a known entity class")
            self.live.add(cls.lower())
            return

        if cmd in MODEL_COMMANDS:
            if args:
                a.models.add(args[0].text)
            return

        if cmd == 'ent_setname':
            if args:
                a.add_name(args[0].text, ln, 'ent_setname')
                self.define_targetname(args[0].text, ln, *self.span(via, args[0]))
            return

        if cmd == 'ent_fire':
            self.ent_fire(args, ln, line, via, c0, c1)
            return

        if cmd == 'ent_keyvalue':
            self.ent_keyvalue(args, ln, via, c0, c1)
            return

        if cmd not in COMMANDS_L and not is_cvar(cmd):
            a.diag(ln, c0, c1, 'info', f"Unknown command '{w0.text}' (typo or undefined alias?)")

    def ent_fire(self, args, ln, line, via, c0, c1):
        a = self.a
        if len(args) < 2:
            a.diag(ln, c0, c1, 'error', 'ent_fire needs a target and an input')
            return
        target, inp = args[0].text, args[1].text.lower()
        tl = target.lower()
        if tl in INPUTS_L and tl not in ENTITIES_L and tl not in {n.lower() for n in a.names}:
            a.diag(ln, *self.span(via, args[0]), 'warning',
                   f"ent_fire target '{target}' looks like an input - is a word missing or doubled?")
        if inp != 'addoutput' or len(args) < 3:
            return
        p = args[2]
        param = p.text if p.quoted else ' '.join(w.text for w in args[2:])
        m = re.match(r'\s*(\S+)\s*(.*)', param)
        if not m:
            return
        key, value = m.group(1).rstrip(';'), _value(m.group(2))
        kl = key.lower()
        span = self.span(via, p)
        if kl == 'hammerid':
            if value in a.hammerids:
                a.diag(ln, *span, 'warning',
                       f"hammerid {value} was already assigned on line {a.hammerids[value]['line']}")
            a.hammerids[value] = {'line': ln, 'cls': tl, 'name': ''}
            self.pending_ids.add(value)
        elif kl == 'classname':
            self.live.discard(tl)
            a.add_name(value, ln, 'classname')
        elif kl == 'targetname':
            a.add_name(value, ln, 'targetname')
            if tl in self.live:
                self.define_targetname(value, ln, *span)
        elif is_output(key):
            self.check_output(value, ln, *span)

    def ent_keyvalue(self, args, ln, via, c0, c1):
        a = self.a
        if len(args) < 3:
            a.diag(ln, c0, c1, 'error', 'ent_keyvalue needs an entity and at least one key/value pair')
            return
        ident = args[0].text
        span = self.span(via, args[0])
        scripted = ident in a.hammerids
        if ident.isdigit():
            if not scripted and int(ident) < 10000:
                a.diag(ln, *span, 'warning',
                       f"hammerid {ident} is never assigned before this line "
                       f"(expected ent_fire <class> addoutput\"hammerid {ident}\")")
            elif ident in self.pending_ids:
                a.diag(ln, *span, 'warning',
                       f"hammerid {ident} was set without a Test_Wait in between - "
                       f"ent_fire is queued, so ent_keyvalue won't find the entity yet")
        pairs = args[1:]
        if len(pairs) % 2:
            last = pairs[-1]
            a.diag(ln, *self.span(via, last), 'warning', f"Key '{last.text}' has no value")
        for i in range(0, len(pairs) - 1, 2):
            key, val = pairs[i], pairs[i + 1]
            kl = key.text.lower()
            v = _value(val.text)
            if kl == 'classname':
                if scripted:
                    self.live.discard(a.hammerids[ident]['cls'])
                    a.hammerids[ident]['cls_new'] = v
                a.add_name(v, ln, 'classname')
            elif kl == 'targetname':
                a.add_name(v, ln, 'targetname')
                if scripted:
                    a.hammerids[ident]['name'] = v
                    self.define_targetname(v, ln, *self.span(via, val))
            elif is_output(key.text):
                self.check_output(v, ln, *self.span(via, val))


def analyze(text):
    return _Checker(text).run()


# --------------------------------------------------------------------------
# Text transforms
# --------------------------------------------------------------------------

def split_statements(line):
    """Return the line's statements as separate lines (comment kept on the last)."""
    stmts, comment = lex_line(line)
    if len(stmts) <= 1:
        return [line]
    out = []
    for st in stmts:
        end = st.sep + 1 if st.sep is not None else st.end
        piece = line[st.start:end].strip()
        if piece:
            out.append(piece)
    if comment is not None:
        out[-1] = out[-1] + ' ' + line[comment:].strip()
    return out


def expand_aliases_line(line, aliases):
    """Replace one-word alias calls with their bodies."""
    if is_end_marker(line):
        return line
    stmts, _ = lex_line(line)
    for st in reversed(stmts):
        if len(st.words) == 1:
            w = st.words[0]
            name = w.text.lower()
            if name in aliases and name != 'alias':
                body = aliases[name][1].strip().rstrip(';').strip()
                line = line[:w.start] + body + line[w.end:]
    return line


# --------------------------------------------------------------------------
# Running scripts and coordinates
# --------------------------------------------------------------------------

def testscript_relpath(path):
    """Path of a script relative to its testscripts folder, with '/' separators.

    D:\\Games\\game\\tf\\testscripts\\Gamemodes\\2Fort\\KOTH.txt -> Gamemodes/2Fort/KOTH.txt
    Returns None when the file isn't inside a folder called testscripts.
    """
    parts = re.split(r'[\\/]+', path)
    for i in range(len(parts) - 2, -1, -1):
        if parts[i].lower() == 'testscripts':
            return '/'.join(parts[i + 1:])
    return None


def run_command(path, template='test_startscript {path}'):
    """The console command that starts the script, or None if it isn't under testscripts."""
    rel = testscript_relpath(path)
    if rel is None:
        return None
    name = re.split(r'[\\/]+', path)[-1]
    return template.replace('{path}', rel).replace('{name}', name)


NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)'


def parse_position(text):
    """Pull (x, y, z) and (pitch, yaw, roll) out of getpos output or plain numbers.

    Understands 'setpos 1 2 3;setang 4 5 6', 'origin "1 2 3"', or just '1 2 3 [4 5 6]'.
    Either part is None when it isn't there.
    """
    pos = ang = None
    m = re.search(rf'setpos(?:_exact)?\s+({NUM})\s+({NUM})\s+({NUM})', text, re.I)
    if m:
        pos = tuple(float(v) for v in m.groups())
    m = re.search(rf'setang(?:_exact)?\s+({NUM})\s+({NUM})(?:\s+({NUM}))?', text, re.I)
    if m:
        ang = tuple(float(v) if v is not None else 0.0 for v in m.groups())
    if pos is None:
        m = re.search(rf'origin\W*({NUM})\s+({NUM})\s+({NUM})', text, re.I)
        if m:
            pos = tuple(float(v) for v in m.groups())
    if ang is None:
        m = re.search(rf'angles\W*({NUM})(?:\s+({NUM}))?(?:\s+({NUM}))?', text, re.I)
        if m:
            ang = tuple(float(v) if v is not None else 0.0 for v in m.groups())
    if pos is None and ang is None:
        nums = [float(v) for v in re.findall(NUM, text)]
        if len(nums) >= 3:
            pos = tuple(nums[:3])
        if len(nums) >= 6:
            ang = tuple(nums[3:6])
    return pos, ang


def format_number(value, decimals=None):
    """Short number text: decimals=None keeps up to 3 places, trailing zeros dropped."""
    if decimals == 0:
        text = str(int(round(value)))
    else:
        text = f'{value:.{3 if decimals is None else decimals}f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def nudge_number(line, col, delta):
    """Add delta to the number at col. Returns (new_line, start, end) or None."""
    for m in re.finditer(rf'(?<![\w.]){NUM}(?![\w])', line):
        if m.start() <= col <= m.end():
            old = m.group()
            places = len(old.split('.')[1]) if '.' in old else 0
            new = format_number(float(old) + delta, places)
            if places and '.' not in new:
                new += '.' + '0' * places
            return line[:m.start()] + new + line[m.end():], m.start(), m.start() + len(new)
    return None


# --------------------------------------------------------------------------
# Launching the game
# --------------------------------------------------------------------------

DEFAULT_LAUNCH_OPTIONS = ('-game tf 440 -sw -w 1920 -h 1080 -port 27016 -novid -dev -console '
                          '-insecure -toconsole -nohltv -nomaster')
LAUNCHER_SCRIPT = 'testscript_pad_launch.txt'


def game_dir_from_script(path):
    """D:\\Games\\game\\tf\\testscripts\\x.txt -> D:\\Games\\game (the folder holding hl2.exe)."""
    parts = re.split(r'[\\/]+', path)
    for i in range(len(parts) - 2, 0, -1):
        if parts[i].lower() == 'testscripts' and parts[i - 1].lower() == 'tf':
            return '\\'.join(parts[:i - 1]) or None
    return None


def guess_map(relpath, maps):
    """Pick the map a script is for from its folder names (Gamemodes/2Fort/KOTH.txt -> ctf_2fort).

    maps: installed map names without .bsp. Returns None when no folder matches.
    """
    by_lower = {m.lower(): m for m in maps}
    folders = [f.lower() for f in relpath.split('/')[:-1]]
    for f in reversed(folders):
        if f in by_lower:
            return by_lower[f]
    for f in reversed(folders):
        hits = sorted(m for m in maps if re.search(rf'(^|_){re.escape(f)}($|_)', m.lower()))
        if hits:
            return hits[0]
    return None


def launcher_script(relpath, map_name, wait):
    """Testscript that loads a map, waits, then starts the real script."""
    return (f'// Written by Testscript-Pad to start {relpath} - safe to delete\n'
            f'sv_cheats 1;\n'
            f'map {map_name};\n'
            f'Test_Wait {format_number(float(wait))};\n'
            f'sv_cheats 1;\n'
            f'test_startscript {relpath};\n'
            f'///\n')


def launch_options(options):
    """Launch options with -game tf added when missing."""
    options = options.strip()
    if not re.search(r'(^|\s)-game\s', options):
        options = '-game tf ' + options
    return options
