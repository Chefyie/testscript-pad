"""Read the entities out of a Source (Orange Box, BSP v20) map file.

Gives Testscript-Pad the names, classnames and hammerids that exist in a map,
so autocomplete, the checker and the status bar know about entities the
script doesn't create itself (flag_blue, door_blue1_2_up, ...).
"""

import os
import re
import struct

ENTITY_LUMP = 0
_cache = {}          # path -> (mtime, MapInfo)


class MapEntity:
    __slots__ = ('classname', 'targetname', 'hammerid', 'origin', 'keys', 'outputs')

    def __init__(self, pairs):
        self.keys = {}
        self.outputs = []
        for k, v in pairs:
            kl = k.lower()
            if kl.startswith('on') or kl == 'outvalue':
                self.outputs.append((k, v.replace('\x1b', ',')))
            else:
                self.keys[kl] = v
        self.classname = self.keys.get('classname', '')
        self.targetname = self.keys.get('targetname', '')
        self.hammerid = self.keys.get('hammerid', '')
        self.origin = self.keys.get('origin', '')

    def describe(self):
        bits = [self.classname or '?']
        if self.targetname:
            bits.append(f"'{self.targetname}'")
        if self.origin:
            bits.append(f'at {self.origin}')
        return ' '.join(bits)


class MapInfo:
    def __init__(self, name, path, entities):
        self.name = name
        self.path = path
        self.entities = entities
        self.by_name = {}
        self.by_hammerid = {}
        self.classnames = set()
        for e in entities:
            if e.targetname:
                self.by_name.setdefault(e.targetname.lower(), []).append(e)
            if e.hammerid:
                self.by_hammerid[e.hammerid] = e
            if e.classname:
                self.classnames.add(e.classname.lower())

    @property
    def names(self):
        """Targetnames in their original spelling, sorted."""
        return sorted({e.targetname for e in self.entities if e.targetname}, key=str.lower)

    def has_target(self, target):
        """Would 'ent_fire <target>' hit something in the map (name or classname, * wildcards)?"""
        t = target.lower()
        if '*' in t:
            pat = re.compile(re.escape(t).replace(r'\*', '.*') + '$')
            return any(pat.match(n) for n in self.by_name) or any(pat.match(c) for c in self.classnames)
        return t in self.by_name or t in self.classnames


def _parse_entities(text):
    entities = []
    pairs = None
    for m in re.finditer(r'"([^"]*)"|([{}])', text):
        quoted, brace = m.groups()
        if brace == '{':
            pairs, key = [], None
        elif brace == '}':
            if pairs is not None:
                entities.append(MapEntity(pairs))
            pairs = None
        elif pairs is not None:
            if key is None:
                key = quoted
            else:
                pairs.append((key, quoted))
                key = None
    return entities


def read_bsp_entities(path):
    """Return the MapEntity list from a .bsp file. Raises ValueError for unsupported files."""
    with open(path, 'rb') as f:
        header = f.read(8 + 16 * 64)
        if len(header) < 8 + 16 or header[:4] != b'VBSP':
            raise ValueError('not a Source map (missing VBSP header)')
        offset, length = struct.unpack_from('<ii', header, 8 + 16 * ENTITY_LUMP)
        f.seek(offset)
        raw = f.read(length)
    if raw[:4] == b'LZMA':
        raise ValueError('compressed entity lump (not used by Orange Box maps)')
    return _parse_entities(raw.decode('latin-1').rstrip('\x00'))


def load_map(game_dir, map_name):
    """MapInfo for tf/maps/<map_name>.bsp, cached until the file changes. None if missing."""
    if not game_dir or not map_name:
        return None
    path = os.path.join(game_dir, 'tf', 'maps', map_name + '.bsp')
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        info = MapInfo(map_name, path, read_bsp_entities(path))
    except (OSError, ValueError, struct.error):
        return None
    _cache[path] = (mtime, info)
    return info
