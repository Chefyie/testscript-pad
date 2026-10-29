"""Connection between Testscript-Pad and a running TF2 (over RCON).

The game only opens its RCON port when started with -usercon and an
rcon_password, so Testscript-Pad adds those when it launches the game. It
binds the port to the machine's network address (which isn't always
127.0.0.1), so the address is looked up from Windows' list of listening
ports for hl2.exe.
"""

import os
import re
import shutil
import subprocess
import sys

import rcon

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=5,
                              creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def game_pids():
    """PIDs of running hl2.exe processes (Windows only)."""
    if sys.platform != 'win32':
        return set()
    out = _run(['tasklist', '/FI', 'IMAGENAME eq hl2.exe', '/FO', 'CSV', '/NH'])
    return {int(m.group(1)) for m in re.finditer(r'^"hl2\.exe","(\d+)"', out, re.I | re.M)}


def find_game_address(port):
    """(host, port) the running game listens on for RCON, or None."""
    pids = game_pids()
    if not pids:
        return None
    found = []
    for line in _run(['netstat', '-ano', '-p', 'tcp']).splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == 'TCP' and parts[3].upper() == 'LISTENING':
            try:
                pid = int(parts[4])
            except ValueError:
                continue
            host, _, p = parts[1].rpartition(':')
            if pid in pids and p.isdigit():
                found.append(('127.0.0.1' if host in ('0.0.0.0', '[::]') else host, int(p)))
    for addr in found:
        if addr[1] == port:
            return addr
    return found[0] if found else None


def port_from_options(options):
    m = re.search(r'(?:^|\s)-port\s+(\d+)', options)
    return int(m.group(1)) if m else 27015


def link_options(options, password):
    """Launch options with what the game link needs (-usercon, console log, rcon password)."""
    extra = []
    if not re.search(r'(^|\s)-usercon(\s|$)', options):
        extra.append('-usercon')
    if not re.search(r'(^|\s)-condebug(\s|$)', options):
        extra.append('-condebug')
    extra.append(f'+rcon_password {password}')
    return (options + ' ' + ' '.join(extra)).strip()


class GameLink:
    def __init__(self, password, port):
        self.password = password
        self.port = port
        self.conn = None
        self.address = None

    @property
    def connected(self):
        return self.conn is not None and self.conn.connected

    def connect(self):
        """Find the running game and log in. Raises rcon.RconError with a readable reason."""
        self.close()
        if not game_pids():
            raise rcon.RconError("TF2 isn't running")
        addr = find_game_address(self.port)
        if addr is None:
            raise rcon.RconError('TF2 has no RCON port open - start it from Testscript-Pad (F9) '
                                 'so it gets -usercon and a password')
        self.address = addr
        self.conn = rcon.Rcon(addr[0], addr[1], self.password).connect()
        return self

    def command(self, cmd):
        """Run a command in the game, connecting first if needed. Returns its output."""
        if not self.connected:
            self.connect()
        try:
            return self.conn.command(cmd)
        except rcon.RconError:
            # the game may have restarted; try one fresh connection
            self.connect()
            return self.conn.command(cmd)

    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.conn = None


# --------------------------------------------------------------------------
# Testscript-Pad plugin (plugin/testscript_pad_plugin.cpp)
# --------------------------------------------------------------------------

PLUGIN_FILES = ('testscript_pad.dll', 'testscript_pad.vdf')
ENT_FIELDS = ('classname', 'targetname', 'hammerid', 'origin', 'angles', 'model', 'parentname')


def parse_entities(text, tag='TSP_ENT'):
    """Entities from tsp_ents / tsp_find / tsp_pick output, as dicts of ENT_FIELDS."""
    out = []
    for line in text.splitlines():
        parts = line.rstrip('\r').split('\t')
        if parts[0] == tag and len(parts) > 1 and parts[1] != 'none':
            out.append(dict(zip(ENT_FIELDS, parts[1:] + [''] * len(ENT_FIELDS))))
    return out


def parse_pick(text):
    """(entity dict or None, 'x y z' aim point or None) from tsp_pick output."""
    ents = parse_entities(text, 'TSP_PICK')
    hit = next((l.split('\t')[1].strip() for l in text.splitlines() if l.startswith('TSP_HIT\t')), None)
    return (ents[0] if ents else None), hit


def plugin_error(text):
    """The plugin's TSP_ERROR message, '' when there is none."""
    return next((l.split('\t', 1)[1].strip() for l in text.splitlines() if l.startswith('TSP_ERROR\t')), '')


def plugin_installed(game_dir):
    return bool(game_dir) and os.path.isfile(os.path.join(game_dir, 'tf', 'addons', PLUGIN_FILES[0]))


def install_plugin(source_dir, game_dir):
    """Copy the plugin DLL and .vdf into <game>/tf/addons. Raises OSError (e.g. TF2 is running)."""
    addons = os.path.join(game_dir, 'tf', 'addons')
    os.makedirs(addons, exist_ok=True)
    for name in PLUGIN_FILES:
        shutil.copyfile(os.path.join(source_dir, name), os.path.join(addons, name))
