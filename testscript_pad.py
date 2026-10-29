"""Testscript-Pad - an editor for Orange Box / TF2 testscripts.

Run:  pythonw testscript_pad.py [files...]
"""

import json
import os
import re
import secrets
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter import font as tkfont

import gamelink
import mapdata
import rcon
import tslang

APP_NAME = 'Testscript-Pad'
VERSION = '1.0'
CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, 'settings.json')
DEFAULT_DIR = r'D:\Games\game\tf\testscripts'
FILETYPES = [('Testscripts', '*.txt'), ('All files', '*.*')]

SYNTAX_TAGS = ['string', 'command', 'testcmd', 'cvar', 'alias', 'aliasdef', 'unknown',
               'entity', 'target', 'targetdef', 'special', 'input', 'output', 'key',
               'number', 'model', 'hammerid', 'sep', 'comment', 'endmark', 'dead']

THEMES = {
    'dark': {
        'bg': '#1e1f22', 'fg': '#d4d4d4', 'gutter_bg': '#18191b', 'gutter_fg': '#5f636a',
        'gutter_cur': '#c8c8c8', 'select': '#264f78', 'cursor': '#ffffff', 'curline': '#25272b',
        'panel_bg': '#25262a', 'panel_fg': '#cfcfcf', 'found': '#5a4a00',
        'accent': '#cf6a32', 'border': '#2e3035', 'muted': '#8b8f96', 'hover': '#2f3136',
        'scroll': '#3c3f45', 'scroll_hover': '#50545b', 'status_bg': '#b8582a', 'status_fg': '#ffffff',
        'ok': '#6cc070',
        'error': '#f14c4c', 'warning': '#e5b93c', 'info': '#4a9fe0',
        'string': ('#ce9178',), 'command': ('#569cd6', 'bold'), 'testcmd': ('#c586c0', 'bold'),
        'cvar': ('#4fc1ff',), 'alias': ('#dcdcaa', 'bold'), 'aliasdef': ('#dcdcaa', 'bold underline'),
        'unknown': ('#d4d4d4',), 'entity': ('#4ec9b0',), 'target': ('#9cdcfe',),
        'targetdef': ('#9cdcfe', 'bold'), 'special': ('#ff6e8a',), 'input': ('#e5c07b',),
        'output': ('#d7a5ff', 'bold'), 'key': ('#f39a6b',), 'number': ('#b5cea8',),
        'model': ('#d7ba7d',), 'hammerid': ('#7ee0e0', 'bold'), 'sep': ('#7a7a7a',),
        'comment': ('#6a9955', 'italic'), 'endmark': ('#ff5f5f', 'bold'), 'dead': ('#555555', 'italic'),
    },
    'light': {
        'bg': '#ffffff', 'fg': '#1e1e1e', 'gutter_bg': '#f3f3f3', 'gutter_fg': '#9a9a9a',
        'gutter_cur': '#202020', 'select': '#add6ff', 'cursor': '#000000', 'curline': '#f5f7fa',
        'panel_bg': '#f3f3f3', 'panel_fg': '#202020', 'found': '#ffe58a',
        'accent': '#cf6a32', 'border': '#dadada', 'muted': '#6e6e6e', 'hover': '#e6e6e6',
        'scroll': '#c6c6c6', 'scroll_hover': '#a6a6a6', 'status_bg': '#cf6a32', 'status_fg': '#ffffff',
        'ok': '#2e8b3a',
        'error': '#d32f2f', 'warning': '#b8860b', 'info': '#1e6fc0',
        'string': ('#a31515',), 'command': ('#0000cc', 'bold'), 'testcmd': ('#8a1bb5', 'bold'),
        'cvar': ('#0070c1',), 'alias': ('#795e26', 'bold'), 'aliasdef': ('#795e26', 'bold underline'),
        'unknown': ('#1e1e1e',), 'entity': ('#267f99',), 'target': ('#001080',),
        'targetdef': ('#001080', 'bold'), 'special': ('#c2185b',), 'input': ('#9c5d00',),
        'output': ('#7b30d0', 'bold'), 'key': ('#c4501b',), 'number': ('#098658',),
        'model': ('#8b6c00',), 'hammerid': ('#007a7a', 'bold'), 'sep': ('#909090',),
        'comment': ('#008000', 'italic'), 'endmark': ('#d00000', 'bold'), 'dead': ('#b0b0b0', 'italic'),
    },
}

TEMPLATES = {
    'Blank script': '// {name}\n\n///\n',
    'Gamemode skeleton': '''// {name}
// ---- Aliases (one command each) ----
alias a"give logic_relay;
alias b"give game_text;

// ---- Clean up the map ----
ent_fire team_round_timer kill;
noclip;
setpos 0 0 0;
setang 90 90;
Test_Wait .1;

// ---- Entities ----
a;
ent_fire logic_relay addoutput"classname my_relay;
ent_fire my_relay addoutput"OnTrigger my_text,display;
Test_Wait .1;
b;
ent_fire game_text addoutput"classname my_text;
ent_fire my_text addoutput"message Hello from {name}!;
ent_fire my_text addoutput"x -1;
ent_fire my_text addoutput"y .14;
ent_fire my_text addoutput"holdtime 5;
ent_fire my_text addoutput"spawnflags 1;
Test_Wait .1;

// ---- Round timer ----
give team_round_timer;ent_fire team_round_timer addoutput"hammerid 1";test_wait .1;ent_keyvalue 1 classname my_timer OnRoundStart"my_relay,trigger,,1";

// ---- Credits ----
give game_text_tf;ent_fire game_text_tf addoutput"hammerid 2";test_wait .1;ent_keyvalue 2 classname credits message"{name} script"icon"voice_player;

mp_restartround 1;
///
''',
    'Compact (hammerid) style': '''// {name}
alias a"give logic_relay;
a;ent_fire logic_relay addoutput"hammerid 1";test_wait .1;ent_keyvalue 1 classname player targetname relay1 OnTrigger"!activator,addoutput,targetname someone";
mp_restartround 1;
///
''',
}


# ==========================================================================
# Settings
# ==========================================================================

def begin_undo(text):
    """Start a group of edits that Ctrl+Z undoes in one step."""
    text.edit_separator()
    text.configure(autoseparators=False)


def end_undo(text):
    text.edit_separator()
    text.configure(autoseparators=True)


def set_dark_titlebar(win, dark):
    """Windows 10/11: ask DWM for a dark (or light) title bar."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except (OSError, AttributeError, tk.TclError):
        pass


class Tooltip:
    def __init__(self, widget, text, app):
        self.widget, self.text, self.app = widget, text, app
        self.win = None
        self.job = None
        widget.bind('<Enter>', self._schedule, add=True)
        widget.bind('<Leave>', self._hide, add=True)
        widget.bind('<ButtonPress>', self._hide, add=True)

    def _schedule(self, _e):
        self._hide()
        self.job = self.widget.after(500, self._show)

    def _show(self):
        self.job = None
        t = self.app.theme
        self.win = tk.Toplevel(self.widget)
        self.win.wm_overrideredirect(True)
        tk.Label(self.win, text=self.text, bg=t['panel_bg'], fg=t['panel_fg'], font=self.app.ui_font,
                 padx=8, pady=4, highlightthickness=1, highlightbackground=t['border']).pack()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.win.geometry(f'+{x}+{y}')

    def _hide(self, _e=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.win:
            self.win.destroy()
            self.win = None


class Settings:
    DEFAULTS = {
        'theme': 'dark', 'font_family': 'Consolas', 'font_size': 11, 'recent': [],
        'last_dir': DEFAULT_DIR, 'open_files': [], 'geometry': '1280x800',
        'show_outline': True, 'show_problems': True, 'wrap': False, 'autocomplete': True,
        'outline_width': 230, 'problems_height': 150, 'show_toolbar': True,
        'run_template': 'test_startscript {path}',
        'game_dir': '', 'launch_options': tslang.DEFAULT_LAUNCH_OPTIONS, 'launch_map': '',
        'fallback_map': 'ctf_2fort', 'launch_wait_s': 20, 'reuse_game': True,
        'script_maps': {}, 'game_link': True, 'rcon_password': '',
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass


# ==========================================================================
# Autocomplete popup
# ==========================================================================

class Completer:
    def __init__(self, editor):
        self.ed = editor
        self.win = None
        self.items = []
        self.start = None

    @property
    def visible(self):
        return self.win is not None

    def show(self, items, start_index):
        self.items = items
        self.start = start_index
        if self.win is None:
            self.win = tk.Toplevel(self.ed)
            self.win.wm_overrideredirect(True)
            self.win.attributes('-topmost', True)
            t = self.ed.app.theme
            self.lb = tk.Listbox(self.win, activestyle='none', exportselection=False,
                                 font=self.ed.app.font, bg=t['panel_bg'], fg=t['panel_fg'],
                                 selectbackground=t['select'], selectforeground=t['fg'],
                                 highlightthickness=1, highlightcolor=t['gutter_fg'],
                                 relief='flat', borderwidth=0)
            self.lb.pack(fill='both', expand=True)
            self.lb.bind('<ButtonRelease-1>', lambda e: self.accept())
        self.lb.delete(0, 'end')
        for it in items:
            self.lb.insert('end', it)
        self.lb.configure(height=min(10, len(items)),
                          width=max(18, min(60, max(len(i) for i in items) + 2)))
        self.lb.selection_clear(0, 'end')
        self.lb.selection_set(0)
        self.lb.see(0)
        bbox = self.ed.text.bbox('insert')
        if bbox:
            x = self.ed.text.winfo_rootx() + bbox[0]
            y = self.ed.text.winfo_rooty() + bbox[1] + bbox[3] + 2
            self.win.geometry(f'+{x}+{y}')

    def hide(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None

    def move(self, delta):
        sel = self.lb.curselection()
        i = (sel[0] if sel else 0) + delta
        i = max(0, min(len(self.items) - 1, i))
        self.lb.selection_clear(0, 'end')
        self.lb.selection_set(i)
        self.lb.see(i)

    def accept(self):
        sel = self.lb.curselection()
        if not sel:
            self.hide()
            return
        word = self.items[sel[0]]
        txt = self.ed.text
        begin_undo(txt)
        txt.delete(self.start, 'insert')
        txt.insert(self.start, word)
        end_undo(txt)
        self.hide()
        txt.focus_set()


# ==========================================================================
# Editor tab
# ==========================================================================

class Editor(ttk.Frame):
    def __init__(self, master, app, path=None, content='', encoding='utf-8', newline='\r\n'):
        super().__init__(master)
        self.app = app
        self.path = path
        self.encoding = encoding
        self.newline = newline
        self.analysis = tslang.analyze('')
        self.aliases = frozenset()
        self.end_line = None
        self.diag_lines = {}
        self._dirty = set()
        self._full = False
        self._hl_job = None
        self._an_job = None
        self._gutter_job = None
        self._cursor_job = None
        self._hl_progress = None
        self._modified = False

        self.gutter = tk.Canvas(self, width=48, highlightthickness=0, borderwidth=0)
        self.text = tk.Text(self, wrap='none', undo=True, maxundo=-1, autoseparators=True,
                            borderwidth=0, highlightthickness=0, padx=6, pady=2,
                            font=app.font, insertwidth=2)
        self.vbar = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        self.hbar = ttk.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=self._yscroll, xscrollcommand=self.hbar.set)
        self.gutter.grid(row=0, column=0, sticky='ns')
        self.text.grid(row=0, column=1, sticky='nsew')
        self.vbar.grid(row=0, column=2, sticky='ns')
        self.hbar.grid(row=1, column=1, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self.completer = Completer(self)
        self._install_proxy()
        self.apply_theme()
        self.set_wrap(app.settings['wrap'])

        if content:
            self.text.insert('1.0', content)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self._modified = False
        self.request_full_highlight()
        self.schedule_analysis(10)

        t = self.text
        t.bind('<KeyPress>', self._on_key, add=True)
        t.bind('<KeyRelease>', self._on_key_release, add=True)
        t.bind('<Control-space>', lambda e: (self.complete(force=True), 'break')[1])
        t.bind('<FocusOut>', lambda e: self.after(150, self._maybe_hide_completer))
        t.bind('<Button-1>', lambda e: self.completer.hide(), add=True)
        t.bind('<Configure>', lambda e: self.schedule_gutter())
        t.bind('<Control-MouseWheel>', self._ctrl_wheel)
        self.gutter.bind('<Button-1>', self._gutter_click)
        self.gutter.bind('<MouseWheel>', lambda e: t.yview_scroll(int(-e.delta / 40), 'units'))

    # -- Tk text proxy: see every insert/delete so only changed lines are re-highlighted
    def _install_proxy(self):
        w = self.text._w
        self._orig = w + '_orig'
        self.tk.call('rename', w, self._orig)
        self.tk.createcommand(w, self._proxy)

    def _proxy(self, *args):
        cmd = args[0] if args else ''
        if cmd in ('insert', 'delete', 'replace'):
            try:
                first = int(str(self.tk.call(self._orig, 'index', args[1])).split('.')[0])
            except (tk.TclError, IndexError):
                first = None
            result = self.tk.call((self._orig,) + args)
            if first is not None:
                added = 0
                if cmd == 'insert':
                    added = sum(str(a).count('\n') for a in args[2::2])
                elif cmd == 'replace':
                    added = sum(str(a).count('\n') for a in args[3::2])
                for ln in range(first, first + added + 1):
                    self._dirty.add(ln)
            self._changed()
            return result
        result = self.tk.call((self._orig,) + args)
        if cmd == 'edit' and len(args) > 1 and args[1] in ('undo', 'redo'):
            self.request_full_highlight()
            self._changed()
        elif cmd in ('yview', 'xview', 'see') or (cmd == 'mark' and len(args) > 2 and args[2] == 'insert'):
            self.schedule_gutter()
            self.schedule_cursor()
        return result

    def _changed(self):
        if not self._modified:
            self._modified = True
            self.app.update_tab_title(self)
        if self._hl_job is None:
            self._hl_job = self.after_idle(self._run_highlight)
        self.schedule_analysis()
        self.schedule_gutter()
        self.schedule_cursor()

    # -- state ------------------------------------------------------------
    @property
    def modified(self):
        return self._modified

    def set_saved(self):
        self._modified = False
        self.app.update_tab_title(self)

    @property
    def title(self):
        return os.path.basename(self.path) if self.path else 'Untitled'

    def get_text(self):
        return self.text.get('1.0', 'end-1c')

    # -- theme ------------------------------------------------------------
    def apply_theme(self):
        t = self.app.theme
        f = self.app.font
        self.text.configure(bg=t['bg'], fg=t['fg'], insertbackground=t['cursor'],
                            selectbackground=t['select'], selectforeground=t['fg'],
                            inactiveselectbackground=t['select'], font=f,
                            tabs=(f.measure('    '),))
        self.gutter.configure(bg=t['gutter_bg'])
        self.text.tag_configure('curline', background=t['curline'])
        for name in SYNTAX_TAGS:
            spec = t[name]
            style = spec[1] if len(spec) > 1 else ''
            self.text.tag_configure(name, foreground=spec[0], font=self.app.styled_font(style))
        for sev in ('info', 'warning', 'error'):
            opts = {'underline': True}
            try:
                self.text.tag_configure('lint_' + sev, underlinefg=t[sev], **opts)
            except tk.TclError:
                self.text.tag_configure('lint_' + sev, **opts)
        self.text.tag_configure('found', background=t['found'])
        self.text.tag_configure('flash', background=t['found'])
        # priority: curline lowest, then string, then the rest; selection on top
        self.text.tag_lower('curline')
        self.text.tag_raise('string', 'curline')
        for name in SYNTAX_TAGS[1:]:
            self.text.tag_raise(name)
        self.text.tag_raise('found')
        self.text.tag_raise('flash')
        self.text.tag_raise('sel')
        self.schedule_gutter()

    def set_wrap(self, wrap):
        self.text.configure(wrap='word' if wrap else 'none')
        if wrap:
            self.hbar.grid_remove()
        else:
            self.hbar.grid()

    # -- highlighting -----------------------------------------------------
    def request_full_highlight(self):
        self._full = True
        if self._hl_job is None:
            self._hl_job = self.after_idle(self._run_highlight)

    def _run_highlight(self):
        self._hl_job = None
        if self._full:
            self._full = False
            self._dirty.clear()
            for name in SYNTAX_TAGS:
                self.text.tag_remove(name, '1.0', 'end')
            self._hl_progress = 1
            self._highlight_chunk()
            return
        dirty, self._dirty = self._dirty, set()
        last = self.line_count()
        for ln in sorted(dirty):
            if 1 <= ln <= last:
                self.highlight_line(ln, clear=True)

    def _highlight_chunk(self):
        start = self._hl_progress
        if start is None:
            return
        last = self.line_count()
        stop = min(last, start + 400)
        for ln in range(start, stop + 1):
            self.highlight_line(ln, clear=False)
        if stop < last:
            self._hl_progress = stop + 1
            self.after(1, self._highlight_chunk)
        else:
            self._hl_progress = None

    def highlight_line(self, ln, clear=True):
        t = self.text
        line = t.get(f'{ln}.0', f'{ln}.end')
        if clear:
            for name in SYNTAX_TAGS:
                t.tag_remove(name, f'{ln}.0', f'{ln}.end')
        dead = self.end_line is not None and ln > self.end_line
        for s, e, tag in tslang.highlight_line(line, self.aliases, dead):
            if e > s:
                t.tag_add(tag, f'{ln}.{s}', f'{ln}.{e}')

    def line_count(self):
        return int(self.text.index('end-1c').split('.')[0])

    # -- analysis ---------------------------------------------------------
    def schedule_analysis(self, delay=350):
        if self._an_job is not None:
            self.after_cancel(self._an_job)
        self._an_job = self.after(delay, self._run_analysis)

    def _run_analysis(self):
        self._an_job = None
        a = tslang.analyze(self.get_text(), self.app.mapinfo_for(self))
        self.analysis = a
        aliases = a.alias_names()
        if aliases != self.aliases or a.end_line != self.end_line:
            self.aliases = aliases
            self.end_line = a.end_line
            self.request_full_highlight()
        t = self.text
        for sev in ('info', 'warning', 'error'):
            t.tag_remove('lint_' + sev, '1.0', 'end')
        self.diag_lines = {}
        rank = {'info': 0, 'warning': 1, 'error': 2}
        for d in a.diagnostics:
            if d.end > d.col:
                t.tag_add('lint_' + d.severity, f'{d.line}.{d.col}', f'{d.line}.{d.end}')
            prev = self.diag_lines.get(d.line)
            if prev is None or rank[d.severity] > rank[prev]:
                self.diag_lines[d.line] = d.severity
        self.schedule_gutter()
        self.app.on_analysis(self)

    # -- gutter -----------------------------------------------------------
    def _yscroll(self, first, last):
        self.vbar.set(first, last)
        self.schedule_gutter()

    def schedule_gutter(self):
        if self._gutter_job is None:
            self._gutter_job = self.after_idle(self.redraw_gutter)

    def redraw_gutter(self):
        self._gutter_job = None
        c = self.gutter
        c.delete('all')
        t = self.app.theme
        f = self.app.font
        digits = max(3, len(str(self.line_count())))
        width = f.measure('9' * digits) + 22
        if int(c.cget('width')) != width:
            c.configure(width=width)
        cur = int(self.text.index('insert').split('.')[0])
        idx = self.text.index('@0,0')
        while True:
            info = self.text.dlineinfo(idx)
            if info is None:
                break
            ln = int(idx.split('.')[0])
            y = info[1]
            c.create_text(width - 6, y, anchor='ne', text=str(ln), font=f,
                          fill=t['gutter_cur'] if ln == cur else t['gutter_fg'])
            sev = self.diag_lines.get(ln)
            if sev:
                r = 3
                cy = y + info[3] // 2
                c.create_oval(4, cy - r, 4 + 2 * r, cy + r, fill=t[sev], outline='')
            nxt = self.text.index(f'{idx}+1line')
            if nxt == idx:
                break
            idx = nxt

    def _gutter_click(self, event):
        idx = self.text.index(f'@0,{event.y}')
        ln = idx.split('.')[0]
        self.text.tag_remove('sel', '1.0', 'end')
        self.text.tag_add('sel', f'{ln}.0', f'{ln}.0+1line')
        self.text.mark_set('insert', f'{ln}.0')
        self.text.focus_set()

    # -- cursor / status --------------------------------------------------
    def schedule_cursor(self):
        if self._cursor_job is None:
            self._cursor_job = self.after_idle(self._cursor_moved)

    def _cursor_moved(self):
        self._cursor_job = None
        t = self.text
        t.tag_remove('curline', '1.0', 'end')
        t.tag_add('curline', 'insert linestart', 'insert lineend+1c')
        self.app.update_status(self)

    def cursor_help(self):
        ln, col = map(int, self.text.index('insert').split('.'))
        line = self.text.get(f'{ln}.0', f'{ln}.end')
        for d in self.analysis.diagnostics:
            if d.line == ln and d.col <= col <= d.end:
                return f'{d.severity.upper()}: {d.message}'
        tok = tslang.token_at(line, col, self.aliases)
        if not tok:
            return ''
        kind, word = tok
        if kind == 'alias':
            a = self.analysis.aliases.get(word.lower())
            return f'alias {word} = {a[1]}' if a else ''
        mi = self.analysis.map
        if kind in ('target', 'targetdef', 'entity'):
            defs = self.analysis.names.get(word)
            if defs:
                return f'{word}: named on line ' + ', '.join(str(d[0]) for d in defs[:6])
            ents = mi.by_name.get(word.lower()) if mi else None
            if ents:
                more = f' (+{len(ents) - 1} more with this name)' if len(ents) > 1 else ''
                return f'{word}: {mi.name} entity - {ents[0].describe()}, hammerid {ents[0].hammerid}{more}'
            if kind != 'entity':
                return ''
        if kind == 'hammerid':
            h = self.analysis.hammerids.get(word)
            if h:
                who = h.get('name') or h.get('cls_new') or h.get('cls')
                return f'hammerid {word}: {who} (assigned on line {h["line"]})'
            e = mi.by_hammerid.get(word) if mi else None
            if e:
                return f'hammerid {word}: {mi.name} entity - {e.describe()}'
            return f'hammerid {word}: map entity (not assigned in this script)'
        found = tslang.lookup_help(kind, word)
        if found:
            name, desc = found
            return f'{name} - {desc}' if not desc.startswith(name) else desc
        return ''

    # -- completion -------------------------------------------------------
    def _maybe_hide_completer(self):
        try:
            if self.focus_get() is not self.text:
                self.completer.hide()
        except (KeyError, tk.TclError):
            self.completer.hide()

    def _on_key(self, event):
        c = self.completer
        if c.visible:
            if event.keysym == 'Down':
                c.move(1); return 'break'
            if event.keysym == 'Up':
                c.move(-1); return 'break'
            if event.keysym == 'Next':
                c.move(8); return 'break'
            if event.keysym == 'Prior':
                c.move(-8); return 'break'
            if event.keysym in ('Tab', 'Return', 'KP_Enter'):
                c.accept(); return 'break'
            if event.keysym == 'Escape':
                c.hide(); return 'break'
        return None

    def _on_key_release(self, event):
        if event.keysym in ('Down', 'Up', 'Next', 'Prior', 'Tab', 'Return', 'KP_Enter', 'Escape',
                            'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R',
                            'Left', 'Right', 'Home', 'End'):
            if event.keysym in ('Left', 'Right', 'Home', 'End'):
                self.completer.hide()
            return
        if event.state & 0x4:   # Control held
            return
        if not self.app.settings['autocomplete']:
            return
        if (event.char and (event.char in tslang.WORD_CHARS or event.char in ',"')) \
                or event.keysym == 'BackSpace' or event.char == ' ':
            self.complete(force=False, trigger=event.char)

    def complete(self, force=False, trigger=''):
        ln, col = map(int, self.text.index('insert').split('.'))
        line = self.text.get(f'{ln}.0', f'{ln}.end')
        kind, start = tslang.completion_context(line, col)
        prefix = line[start:col]
        if trigger in (',', '"') and kind in ('target', 'input', 'key'):
            force = True
        if kind is None or (not force and len(prefix) < 1):
            self.completer.hide()
            return
        items = self.candidates(kind)
        pl = prefix.lower()
        first = [i for i in items if i.lower().startswith(pl)]
        rest = [i for i in items if pl and pl in i.lower() and not i.lower().startswith(pl)]
        matches = first + rest
        if not matches or (len(matches) == 1 and matches[0] == prefix):
            self.completer.hide()
            return
        self.completer.show(matches[:200], f'{ln}.{start}')

    def candidates(self, kind):
        a = self.analysis
        names = sorted(a.names, key=str.lower)
        if kind == 'command':
            out = sorted(a.aliases) + list(tslang.COMMANDS) + tslang.COMMON_CVARS
        elif kind == 'target':
            out = names + (a.map.names if a.map else []) + tslang.SPECIAL_TARGETS + sorted(tslang.ENTITIES)
        elif kind == 'entity':
            out = sorted(tslang.ENTITIES)
        elif kind == 'input':
            out = sorted(tslang.INPUTS)
        elif kind == 'key':
            out = sorted(tslang.KEYVALUES, key=str.lower) + list(tslang.OUTPUTS)
        elif kind == 'hammerid':
            out = sorted(a.hammerids, key=lambda k: int(k) if k.isdigit() else 0)
            if a.map:
                out += [e.hammerid for e in a.map.entities if e.targetname and e.hammerid]
        elif kind == 'model':
            out = sorted(a.models) + [m for m in tslang.COMMON_MODELS if m not in a.models]
        else:
            out = []
        seen = set()
        res = []
        for i in out:
            if i.lower() not in seen:
                seen.add(i.lower())
                res.append(i)
        return res

    def _ctrl_wheel(self, event):
        self.app.zoom(1 if event.delta > 0 else -1)
        return 'break'

    # -- editing helpers --------------------------------------------------
    def selected_lines(self):
        t = self.text
        if t.tag_ranges('sel'):
            first = int(t.index('sel.first').split('.')[0])
            last_idx = t.index('sel.last')
            last = int(last_idx.split('.')[0])
            if last_idx.endswith('.0') and last > first:
                last -= 1
        else:
            first = last = int(t.index('insert').split('.')[0])
        return first, last

    def replace_lines(self, first, last, new_lines):
        t = self.text
        begin_undo(t)
        t.delete(f'{first}.0', f'{last}.end')
        t.insert(f'{first}.0', '\n'.join(new_lines))
        end_undo(t)
        t.tag_remove('sel', '1.0', 'end')
        t.tag_add('sel', f'{first}.0', f'{first + len(new_lines) - 1}.end')

    def toggle_comment(self):
        first, last = self.selected_lines()
        lines = [self.text.get(f'{ln}.0', f'{ln}.end') for ln in range(first, last + 1)]
        body = [l for l in lines if l.strip()]
        uncomment = body and all(l.lstrip().startswith('//') and not tslang.is_end_marker(l) for l in body)
        out = []
        for l in lines:
            if not l.strip():
                out.append(l)
            elif uncomment:
                i = l.index('//')
                rest = l[i + 2:]
                out.append(l[:i] + (rest[1:] if rest.startswith(' ') else rest))
            else:
                out.append('// ' + l)
        self.replace_lines(first, last, out)
        return 'break'

    def duplicate_line(self):
        first, last = self.selected_lines()
        block = self.text.get(f'{first}.0', f'{last}.end')
        begin_undo(self.text)
        self.text.insert(f'{last}.end', '\n' + block)
        end_undo(self.text)
        return 'break'

    def move_lines(self, delta):
        first, last = self.selected_lines()
        total = self.line_count()
        if (delta < 0 and first == 1) or (delta > 0 and last >= total):
            return 'break'
        t = self.text
        col = t.index('insert').split('.')[1]
        block = t.get(f'{first}.0', f'{last}.end')
        if delta < 0:
            other = t.get(f'{first - 1}.0', f'{first - 1}.end')
            self.replace_lines(first - 1, last, block.split('\n') + [other])
            nf = first - 1
        else:
            other = t.get(f'{last + 1}.0', f'{last + 1}.end')
            self.replace_lines(first, last + 1, [other] + block.split('\n'))
            nf = first + 1
        n = last - first
        t.tag_remove('sel', '1.0', 'end')
        if n:
            t.tag_add('sel', f'{nf}.0', f'{nf + n}.end')
        t.mark_set('insert', f'{nf}.{col}')
        t.see('insert')
        return 'break'

    def goto_line(self, ln, col=0, end_col=None):
        t = self.text
        t.mark_set('insert', f'{ln}.{col}')
        t.see('insert')
        t.tag_remove('sel', '1.0', 'end')
        if end_col is not None and end_col > col:
            t.tag_add('sel', f'{ln}.{col}', f'{ln}.{end_col}')
        t.focus_set()
        t.tag_add('flash', f'{ln}.0', f'{ln}.end')
        self.after(500, lambda: t.tag_remove('flash', '1.0', 'end'))

    def nudge(self, delta):
        """Ctrl+Alt+Up/Down: add to the number under the cursor."""
        ln, col = map(int, self.text.index('insert').split('.'))
        line = self.text.get(f'{ln}.0', f'{ln}.end')
        res = tslang.nudge_number(line, col, delta)
        if res is None:
            return 'break'
        new_line, start, end = res
        old_end = end - (len(new_line) - len(line))
        t = self.text
        begin_undo(t)
        t.delete(f'{ln}.{start}', f'{ln}.{old_end}')
        t.insert(f'{ln}.{start}', new_line[start:end])
        end_undo(t)
        t.mark_set('insert', f'{ln}.{min(col, end)}')
        return 'break'

    def word_under_cursor(self):
        ln, col = map(int, self.text.index('insert').split('.'))
        line = self.text.get(f'{ln}.0', f'{ln}.end')
        s = col
        while s > 0 and line[s - 1] in tslang.WORD_CHARS:
            s -= 1
        e = col
        while e < len(line) and line[e] in tslang.WORD_CHARS:
            e += 1
        return line[s:e]


# ==========================================================================
# Dialogs
# ==========================================================================

class Dialog(tk.Toplevel):
    def __init__(self, app, title):
        super().__init__(app.root)
        self.app = app
        self.title(title)
        self.transient(app.root)
        self.resizable(True, True)
        self.configure(bg=app.theme['panel_bg'])
        set_dark_titlebar(self, app.settings['theme'] == 'dark')
        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill='both', expand=True)
        self.bind('<Escape>', lambda e: self.destroy())

    def center(self):
        self.update_idletasks()
        r = self.app.root
        x = r.winfo_rootx() + (r.winfo_width() - self.winfo_width()) // 2
        y = r.winfo_rooty() + (r.winfo_height() - self.winfo_height()) // 3
        self.geometry(f'+{max(0, x)}+{max(0, y)}')


def quote_value(v):
    return f'"{v}"'


class EntityDialog(Dialog):
    """Builds the spawn + rename + keyvalues + outputs block for an entity."""

    def __init__(self, app, editor):
        super().__init__(app, 'Insert entity')
        self.ed = editor
        b = self.body
        a = editor.analysis
        self.cls = tk.StringVar(value='logic_relay')
        self.name = tk.StringVar(value='')
        self.role = tk.StringVar(value='classname')
        self.style = tk.StringVar(value='compact')
        self.spawn = tk.StringVar(value='give')
        self.hid = tk.StringVar(value=str(a.next_hammerid()))
        self.alias = tk.StringVar(value='')

        row = 0
        ttk.Label(b, text='Entity class').grid(row=row, column=0, sticky='w')
        cb = ttk.Combobox(b, textvariable=self.cls, values=sorted(tslang.ENTITIES), width=34)
        cb.grid(row=row, column=1, sticky='ew', columnspan=3)
        row += 1
        ttk.Label(b, text='Name').grid(row=row, column=0, sticky='w')
        ttk.Entry(b, textvariable=self.name, width=36).grid(row=row, column=1, sticky='ew', columnspan=3)
        row += 1
        ttk.Label(b, text='Name sets').grid(row=row, column=0, sticky='w')
        rf = ttk.Frame(b)
        rf.grid(row=row, column=1, columnspan=3, sticky='w')
        for val, txt in (('classname', 'classname'), ('targetname', 'targetname'),
                         ('both', 'targetname + classname'), ('player', 'targetname + classname player')):
            ttk.Radiobutton(rf, text=txt, value=val, variable=self.role, command=self.refresh).pack(side='left', padx=(0, 8))
        row += 1
        ttk.Label(b, text='Style').grid(row=row, column=0, sticky='w')
        sf = ttk.Frame(b)
        sf.grid(row=row, column=1, columnspan=3, sticky='w')
        ttk.Radiobutton(sf, text='Compact (hammerid + ent_keyvalue)', value='compact',
                        variable=self.style, command=self.refresh).pack(side='left', padx=(0, 8))
        ttk.Radiobutton(sf, text='Step by step (ent_fire addoutput)', value='steps',
                        variable=self.style, command=self.refresh).pack(side='left')
        row += 1
        ttk.Label(b, text='Spawn with').grid(row=row, column=0, sticky='w')
        pf = ttk.Frame(b)
        pf.grid(row=row, column=1, sticky='w')
        ttk.Radiobutton(pf, text='give', value='give', variable=self.spawn, command=self.refresh).pack(side='left')
        ttk.Radiobutton(pf, text='ent_create', value='ent_create', variable=self.spawn, command=self.refresh).pack(side='left', padx=6)
        ttk.Label(b, text='Hammer ID').grid(row=row, column=2, sticky='e')
        ttk.Spinbox(b, from_=1, to=999999, textvariable=self.hid, width=8, command=self.refresh).grid(row=row, column=3, sticky='w')
        row += 1
        ttk.Label(b, text='Spawn alias').grid(row=row, column=0, sticky='w')
        al = ttk.Combobox(b, textvariable=self.alias, width=12,
                          values=[''] + sorted(editor.analysis.aliases))
        al.grid(row=row, column=1, sticky='w')
        ttk.Label(b, text='(optional: use an alias instead of the give line)').grid(row=row, column=2, columnspan=2, sticky='w')
        row += 1
        ttk.Label(b, text='Keyvalues  (one per line:  key value)').grid(row=row, column=0, columnspan=4, sticky='w', pady=(8, 0))
        row += 1
        self.kv = tk.Text(b, height=5, width=60, font=app.font, undo=True, **app.text_opts())
        self.kv.grid(row=row, column=0, columnspan=4, sticky='nsew')
        row += 1
        ttk.Label(b, text='Outputs  (one per line:  OnTrigger target,input,parameter,delay)').grid(row=row, column=0, columnspan=4, sticky='w', pady=(8, 0))
        row += 1
        self.outs = tk.Text(b, height=5, width=60, font=app.font, undo=True, **app.text_opts())
        self.outs.grid(row=row, column=0, columnspan=4, sticky='nsew')
        row += 1
        ttk.Label(b, text='Preview').grid(row=row, column=0, sticky='w', pady=(8, 0))
        row += 1
        self.preview = tk.Text(b, height=8, width=60, font=app.font, state='disabled', wrap='none',
                               **app.text_opts())
        self.preview.grid(row=row, column=0, columnspan=4, sticky='nsew')
        b.rowconfigure(row, weight=1)
        b.columnconfigure(1, weight=1)
        row += 1
        bf = ttk.Frame(b)
        bf.grid(row=row, column=0, columnspan=4, sticky='e', pady=(10, 0))
        ttk.Button(bf, text='Insert', command=self.insert).pack(side='right')
        ttk.Button(bf, text='Cancel', command=self.destroy).pack(side='right', padx=6)

        for v in (self.cls, self.name, self.hid, self.alias):
            v.trace_add('write', lambda *_: self.refresh())
        for w in (self.kv, self.outs):
            w.bind('<KeyRelease>', lambda e: self.refresh())
        cb.bind('<<ComboboxSelected>>', lambda e: self._default_kv())
        self._default_kv()
        self.center()
        self.name_focus = b.grid_slaves(row=1, column=1)[0]
        self.name_focus.focus_set()

    DEFAULT_KV = {
        'game_text': 'message Hello!\nx -1\ny .14\nholdtime 5\ncolor 255 255 255\nchannel 1\nspawnflags 1',
        'game_text_tf': 'message Script by you\nicon voice_player',
        'math_counter': 'min 0\nmax 8',
        'logic_timer': 'refiretime 1',
        'trigger_multiple': 'origin 0 0 0\nmins -64 -64 0\nmaxs 64 64 128\nsolid 2\nspawnflags 1',
        'func_capturezone': 'origin 0 0 0\nmins -64 -64 0\nmaxs 64 64 128\nsolid 2',
        'func_wall': 'origin 0 0 0\nmins 0 0 0\nmaxs 128 128 128\nsolid 2',
        'item_teamflag': 'origin 0 0 0\nGameType 0',
        'path_track': 'origin 0 0 0\ntarget next_track',
        'func_train': 'origin 0 0 0\ntarget first_track\nspeed 60\nmodel .',
        'filter_activator_name': 'filtername someone',
        'env_explosion': 'origin 0 0 0\niMagnitude 1\nspawnflags 2',
    }
    DEFAULT_OUT = {
        'logic_relay': 'OnTrigger !activator,addoutput,targetname someone',
        'team_round_timer': 'OnRoundStart my_relay,trigger,,1',
        'trigger_multiple': 'OnStartTouch !activator,addoutput,targetname inside',
        'logic_timer': 'OnTimer my_text,display',
        'filter_activator_tfteam': 'OnPass my_relay,trigger',
        'item_teamflag': 'OnCapture my_counter,add,1',
    }

    def _default_kv(self):
        cls = self.cls.get()
        self.kv.delete('1.0', 'end')
        self.kv.insert('1.0', self.DEFAULT_KV.get(cls, ''))
        self.outs.delete('1.0', 'end')
        self.outs.insert('1.0', self.DEFAULT_OUT.get(cls, ''))
        self.refresh()

    def _pairs(self):
        kv = []
        for l in self.kv.get('1.0', 'end').splitlines():
            l = l.strip()
            if l:
                k, _, v = l.partition(' ')
                kv.append((k, v.strip()))
        outs = []
        for l in self.outs.get('1.0', 'end').splitlines():
            l = l.strip()
            if l:
                k, _, v = l.partition(' ')
                outs.append((k, v.strip().replace(' ,', ',').replace(', ', ',')))
        return kv, outs

    def build(self):
        cls = self.cls.get().strip() or 'logic_relay'
        name = self.name.get().strip() or cls.split('_')[-1] + '1'
        role = self.role.get()
        kv, outs = self._pairs()
        spawn = self.alias.get().strip() or f'{self.spawn.get()} {cls}'
        names = []
        if role in ('targetname', 'both', 'player'):
            names.append(('targetname', name))
        if role in ('classname', 'both'):
            names.append(('classname', name))
        if role == 'player':
            names.append(('classname', 'player'))
        lines = []
        if self.style.get() == 'compact':
            hid = self.hid.get().strip() or '1'
            parts = [f'{k} {v}' if (v and ' ' not in v and '"' not in v) else f'{k}{quote_value(v)}'
                     for k, v in names + kv]
            out_strs = [f'{k}{quote_value(v)}' for k, v in outs]
            first = f'{spawn};ent_fire {cls} addoutput"hammerid {hid}";test_wait .1;ent_keyvalue {hid}'
            if parts:
                first += ' ' + ' '.join(parts)
            if out_strs[:4]:
                first += ' ' + ''.join(out_strs[:4])
            lines.append(first + ';')
            tail = out_strs[4:]
            for i in range(0, len(tail), 4):
                lines.append(f'ent_keyvalue {hid} ' + ''.join(tail[i:i + 4]) + ';')
        else:
            lines.append(f'{spawn};')
            ref = cls
            for k, v in names:
                if k == 'classname' and v == 'player':
                    continue
                lines.append(f'ent_fire {ref} addoutput"{k} {v};')
                ref = v
            for k, v in kv:
                lines.append(f'ent_fire {ref} addoutput"{k} {v};')
            for k, v in outs:
                lines.append(f'ent_fire {ref} addoutput"{k} {v};')
            if role == 'player':
                lines.append(f'ent_fire {ref} addoutput"classname player;')
            lines.append('Test_Wait .1;')
        return '\n'.join(lines)

    def refresh(self):
        try:
            code = self.build()
        except tk.TclError:
            return
        p = self.preview
        p.configure(state='normal')
        p.delete('1.0', 'end')
        p.insert('1.0', code)
        p.configure(state='disabled')

    def insert(self):
        self.app.insert_block(self.ed, self.build())
        self.destroy()


class OutputDialog(Dialog):
    def __init__(self, app, editor):
        super().__init__(app, 'Insert output')
        self.ed = editor
        b = self.body
        a = editor.analysis
        names = sorted(a.names, key=str.lower)
        self.fmt = tk.StringVar(value='ent_fire')
        self.entity = tk.StringVar(value=names[0] if names else '')
        self.output = tk.StringVar(value='OnTrigger')
        self.target = tk.StringVar(value='')
        self.input = tk.StringVar(value='trigger')
        self.param = tk.StringVar(value='')
        self.delay = tk.StringVar(value='')
        self.times = tk.StringVar(value='')
        fields = [
            ('Fire on entity', self.entity, names + sorted(tslang.ENTITIES)),
            ('Output', self.output, list(tslang.OUTPUTS)),
            ('Target', self.target, names + tslang.SPECIAL_TARGETS + sorted(tslang.ENTITIES)),
            ('Input', self.input, sorted(tslang.INPUTS)),
            ('Parameter', self.param, None),
            ('Delay (s)', self.delay, None),
            ('Times (-1 = always)', self.times, None),
        ]
        ff = ttk.Frame(b)
        ff.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
        ttk.Label(ff, text='Format').pack(side='left')
        for val, txt in (('ent_fire', 'ent_fire <entity> addoutput"..."'),
                         ('kv', 'ent_keyvalue pair  Output"..."'),
                         ('raw', 'raw  target,input,...')):
            ttk.Radiobutton(ff, text=txt, value=val, variable=self.fmt, command=self.refresh).pack(side='left', padx=6)
        for r, (label, var, values) in enumerate(fields, 1):
            ttk.Label(b, text=label).grid(row=r, column=0, sticky='w', pady=1)
            w = ttk.Combobox(b, textvariable=var, values=values, width=40) if values is not None \
                else ttk.Entry(b, textvariable=var, width=42)
            w.grid(row=r, column=1, sticky='ew', pady=1)
            var.trace_add('write', lambda *_: self.refresh())
        r = len(fields) + 1
        self.preview = ttk.Label(b, text='', font=app.font)
        self.preview.grid(row=r, column=0, columnspan=2, sticky='w', pady=8)
        bf = ttk.Frame(b)
        bf.grid(row=r + 1, column=0, columnspan=2, sticky='e')
        ttk.Button(bf, text='Insert', command=self.insert).pack(side='right')
        ttk.Button(bf, text='Cancel', command=self.destroy).pack(side='right', padx=6)
        b.columnconfigure(1, weight=1)
        self.refresh()
        self.center()

    def build(self):
        fields = [self.target.get().strip(), self.input.get().strip(), self.param.get(),
                  self.delay.get().strip(), self.times.get().strip()]
        while len(fields) > 2 and not fields[-1]:
            fields.pop()
        value = ','.join(fields)
        out = self.output.get().strip()
        fmt = self.fmt.get()
        if fmt == 'ent_fire':
            return f'ent_fire {self.entity.get().strip()} addoutput"{out} {value};'
        if fmt == 'kv':
            return f'{out}"{value}"'
        return value

    def refresh(self):
        self.preview.configure(text=self.build())

    def insert(self):
        code = self.build()
        if self.fmt.get() == 'ent_fire':
            self.app.insert_block(self.ed, code)
        else:
            self.ed.text.insert('insert', code)
        self.destroy()


class CoordDialog(Dialog):
    """Turns getpos output (or numbers) into origin/angles/setpos text."""

    FORMATS = [
        ('kv', 'origin"x y z"   (ent_keyvalue / ent_create pair)'),
        ('ent_fire', 'ent_fire <name> addoutput"origin x y z;'),
        ('output', 'addoutput,origin x y z   (inside an output)'),
        ('setpos', 'setpos x y z;setang p y r;'),
        ('plain', 'x y z'),
    ]

    def __init__(self, app, editor):
        super().__init__(app, 'Coordinates')
        self.ed = editor
        b = self.body
        names = sorted(editor.analysis.names, key=str.lower)
        self.paste = tk.StringVar()
        self.pos = [tk.StringVar(value='0') for _ in range(3)]
        self.ang = [tk.StringVar(value='0') for _ in range(3)]
        self.offset = [tk.StringVar(value='0') for _ in range(3)]
        self.with_angles = tk.BooleanVar(value=False)
        self.decimals = tk.StringVar(value='whole numbers')
        self.fmt = tk.StringVar(value='kv')
        self.name = tk.StringVar(value=editor.word_under_cursor() if editor.word_under_cursor() in names else
                                 (names[0] if names else 'my_entity'))

        ttk.Label(b, text='Paste getpos output, or click From game to read your position from TF2').grid(
            row=0, column=0, columnspan=8, sticky='w')
        pe = ttk.Entry(b, textvariable=self.paste, width=70)
        pe.grid(row=1, column=0, columnspan=5, sticky='ew', pady=(2, 8))
        ttk.Button(b, text='Paste', command=self.paste_clipboard).grid(row=1, column=5, padx=(6, 0), pady=(2, 8))
        ttk.Button(b, text='From line', command=self.from_line).grid(row=1, column=6, padx=(6, 0), pady=(2, 8))
        Tooltip(b.grid_slaves(row=1, column=6)[0], 'Read the origin/angles on the cursor line', app)
        ttk.Button(b, text='From game', command=self.from_game).grid(row=1, column=7, padx=(6, 0), pady=(2, 8))
        Tooltip(b.grid_slaves(row=1, column=7)[0], 'Ask the running game where you are (getpos)', app)

        for r, (label, vars_, heads) in enumerate((
                ('Position', self.pos, ('X', 'Y', 'Z')),
                ('Offset', self.offset, ('+X', '+Y', '+Z')),
                ('Angles', self.ang, ('Pitch', 'Yaw', 'Roll'))), 2):
            ttk.Label(b, text=label).grid(row=r, column=0, sticky='w', pady=2)
            f = ttk.Frame(b)
            f.grid(row=r, column=1, columnspan=6, sticky='w', pady=2)
            for var, head in zip(vars_, heads):
                ttk.Label(f, text=head, width=6, anchor='e').pack(side='left')
                ttk.Entry(f, textvariable=var, width=13).pack(side='left', padx=(4, 10))
        of = ttk.Frame(b)
        of.grid(row=5, column=1, columnspan=6, sticky='w', pady=(6, 0))
        ttk.Checkbutton(of, text='Include angles', variable=self.with_angles,
                        command=self.refresh).pack(side='left', padx=(6, 20))
        ttk.Label(of, text='Round to').pack(side='left')
        ttk.Combobox(of, textvariable=self.decimals, state='readonly', width=14,
                     values=['whole numbers', '1 decimal', '2 decimals', 'as is']).pack(side='left', padx=6)

        ttk.Label(b, text='Write as').grid(row=6, column=0, sticky='nw', pady=(10, 0))
        ff = ttk.Frame(b)
        ff.grid(row=6, column=1, columnspan=6, sticky='w', pady=(10, 0))
        for val, txt in self.FORMATS:
            ttk.Radiobutton(ff, text=txt, value=val, variable=self.fmt, command=self.refresh).pack(anchor='w')
        ttk.Label(b, text='Entity name').grid(row=7, column=0, sticky='w', pady=(6, 0))
        ttk.Combobox(b, textvariable=self.name, values=names, width=30).grid(
            row=7, column=1, columnspan=4, sticky='w', pady=(6, 0))

        self.preview = tk.Text(b, height=3, width=70, font=app.font, wrap='none', **app.text_opts())
        self.preview.grid(row=8, column=0, columnspan=7, sticky='nsew', pady=(10, 0))
        self.preview.configure(state='disabled')
        bf = ttk.Frame(b)
        bf.grid(row=9, column=0, columnspan=7, sticky='e', pady=(10, 0))
        ttk.Button(bf, text='Insert', command=self.insert).pack(side='right')
        ttk.Button(bf, text='Copy', command=self.copy).pack(side='right', padx=6)
        ttk.Button(bf, text='Close', command=self.destroy).pack(side='right')
        b.columnconfigure(4, weight=1)
        b.rowconfigure(8, weight=1)

        self.paste.trace_add('write', lambda *_: self.parse(self.paste.get()))
        for v in self.pos + self.ang + self.offset + [self.decimals, self.name]:
            v.trace_add('write', lambda *_: self.refresh())
        # start from getpos output on the clipboard, or the cursor line
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            clip = ''
        if re.search(r'setpos', clip, re.I):
            self.paste.set(clip.strip())
        else:
            self.from_line(quiet=True)
        self.refresh()
        self.center()
        pe.focus_set()

    def paste_clipboard(self):
        try:
            self.paste.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def from_game(self):
        try:
            text = self.app.game_command('getpos')
        except rcon.RconError as e:
            messagebox.showwarning(APP_NAME, f"Couldn't read your position from TF2:\n\n{e}", parent=self)
            return
        if 'setpos' not in text:
            messagebox.showwarning(APP_NAME, f'TF2 answered something unexpected:\n\n{text[:300]}', parent=self)
            return
        self.paste.set(text.strip())

    def from_line(self, quiet=False):
        line = self.ed.text.get('insert linestart', 'insert lineend')
        pos, ang = tslang.parse_position(line) if re.search(r'origin|angles|setpos|setang', line, re.I) else (None, None)
        if pos is None and ang is None:
            if not quiet:
                self.app.set_status_message('No origin/angles on the cursor line')
            return
        self.parse(line)

    def parse(self, text):
        pos, ang = tslang.parse_position(text)
        if pos:
            for var, v in zip(self.pos, pos):
                var.set(tslang.format_number(v))
        if ang:
            for var, v in zip(self.ang, ang):
                var.set(tslang.format_number(v))
            self.with_angles.set(True)
        self.refresh()

    def _vals(self, vars_, offsets=None):
        places = {'whole numbers': 0, '1 decimal': 1, '2 decimals': 2}.get(self.decimals.get())
        out = []
        for i, var in enumerate(vars_):
            try:
                v = float(var.get() or 0)
                if offsets:
                    v += float(offsets[i].get() or 0)
            except ValueError:
                return None
            out.append(tslang.format_number(v, places))
        return ' '.join(out)

    def build(self):
        pos = self._vals(self.pos, self.offset)
        ang = self._vals(self.ang)
        if pos is None or ang is None:
            return '(numbers only, please)'
        angles = self.with_angles.get()
        name = self.name.get().strip() or 'my_entity'
        fmt = self.fmt.get()
        if fmt == 'kv':
            return f'origin"{pos}"' + (f' angles"{ang}"' if angles else '')
        if fmt == 'ent_fire':
            code = f'ent_fire {name} addoutput"origin {pos};'
            return code + (f'\nent_fire {name} addoutput"angles {ang};' if angles else '')
        if fmt == 'output':
            return f'{name},addoutput,origin {pos}' + (f'\n{name},addoutput,angles {ang}' if angles else '')
        if fmt == 'setpos':
            return f'setpos {pos};' + (f'setang {ang};' if angles else '')
        return pos + (f'\n{ang}' if angles else '')

    def refresh(self):
        p = self.preview
        p.configure(state='normal')
        p.delete('1.0', 'end')
        p.insert('1.0', self.build())
        p.configure(state='disabled')

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.build())
        self.app.set_status_message('Copied coordinates')

    def insert(self):
        code = self.build()
        if self.fmt.get() in ('ent_fire', 'setpos'):
            self.app.insert_block(self.ed, code)
        else:
            self.ed.text.insert('insert', code.replace('\n', ' '))
        self.destroy()


class GameSettingsDialog(Dialog):
    """Where the game is and how Run in game starts it."""

    AUTO_MAP = '(auto - from the script folder)'
    NO_MAP = '(none - run the script at startup)'

    def __init__(self, app, script_path=None):
        super().__init__(app, 'Game settings')
        b = self.body
        st = app.settings
        self.detected = tslang.game_dir_from_script(script_path) if script_path else None
        self.game_dir = tk.StringVar(value=st['game_dir'])
        self.options = tk.StringVar(value=st['launch_options'])
        self.map = tk.StringVar(value={'': self.AUTO_MAP, '-': self.NO_MAP}.get(st['launch_map'], st['launch_map']))
        self.fallback = tk.StringVar(value=st['fallback_map'])
        self.wait = tk.StringVar(value=tslang.format_number(float(st['launch_wait_s'])))
        self.reuse = tk.BooleanVar(value=st['reuse_game'])
        self.template = tk.StringVar(value=st['run_template'])

        r = 0
        ttk.Label(b, text='Game folder (the one with hl2.exe)').grid(row=r, column=0, sticky='w')
        r += 1
        gf = ttk.Frame(b)
        gf.grid(row=r, column=0, columnspan=3, sticky='ew')
        ttk.Entry(gf, textvariable=self.game_dir, width=60).pack(side='left', fill='x', expand=True)
        ttk.Button(gf, text='Browse...', command=self.browse).pack(side='left', padx=(6, 0))
        r += 1
        self.dir_status = ttk.Label(b, text='')
        self.dir_status.grid(row=r, column=0, columnspan=3, sticky='w', pady=(2, 10))
        r += 1
        ttk.Label(b, text='Launch options  (-testscript is added for you)').grid(row=r, column=0, sticky='w')
        r += 1
        of = ttk.Frame(b)
        of.grid(row=r, column=0, columnspan=3, sticky='ew', pady=(0, 10))
        ttk.Entry(of, textvariable=self.options, width=60).pack(side='left', fill='x', expand=True)
        ttk.Button(of, text='Reset', command=lambda: self.options.set(tslang.DEFAULT_LAUNCH_OPTIONS)).pack(
            side='left', padx=(6, 0))
        r += 1
        ttk.Label(b, text='Map to load').grid(row=r, column=0, sticky='w')
        self.map_box = ttk.Combobox(b, textvariable=self.map, width=36)
        self.map_box.grid(row=r, column=1, sticky='w', padx=6, pady=2)
        r += 1
        ttk.Label(b, text='Map when the folder has no match').grid(row=r, column=0, sticky='w')
        self.fallback_box = ttk.Combobox(b, textvariable=self.fallback, width=36)
        self.fallback_box.grid(row=r, column=1, sticky='w', padx=6, pady=2)
        r += 1
        ttk.Label(b, text='Seconds to wait before the script starts').grid(row=r, column=0, sticky='w')
        ttk.Spinbox(b, from_=0, to=120, increment=1, textvariable=self.wait, width=6).grid(
            row=r, column=1, sticky='w', padx=6, pady=2)
        r += 1
        ttk.Checkbutton(b, text='If the game is already running, run the script in it',
                        variable=self.reuse).grid(row=r, column=0, columnspan=3, sticky='w', pady=(8, 2))
        r += 1
        self.link = tk.BooleanVar(value=st['game_link'])
        ttk.Checkbutton(b, text='Game link: start TF2 with RCON on (-usercon, console log, a private password) '
                                'for the game console and "From game"',
                        variable=self.link).grid(row=r, column=0, columnspan=3, sticky='w', pady=2)
        r += 1
        ttk.Label(b, text='Console command copied to the clipboard  ({path} = path from testscripts, {name} = file name)').grid(
            row=r, column=0, columnspan=3, sticky='w', pady=(10, 0))
        r += 1
        ttk.Entry(b, textvariable=self.template, width=60).grid(row=r, column=0, columnspan=3, sticky='ew')
        r += 1
        bf = ttk.Frame(b)
        bf.grid(row=r, column=0, columnspan=3, sticky='e', pady=(14, 0))
        ttk.Button(bf, text='Save', command=self.save).pack(side='right')
        ttk.Button(bf, text='Cancel', command=self.destroy).pack(side='right', padx=6)
        b.columnconfigure(2, weight=1)
        self.game_dir.trace_add('write', lambda *_: self.check_dir())
        self.check_dir()
        self.center()

    def effective_dir(self):
        return self.game_dir.get().strip() or self.detected or ''

    def check_dir(self):
        d = self.effective_dir()
        ok = bool(d) and os.path.isfile(os.path.join(d, 'hl2.exe'))
        where = 'detected from the script: ' + d if not self.game_dir.get().strip() and d else d
        if not d:
            msg = 'Not set - pick the folder that contains hl2.exe'
        elif ok:
            msg = f'✔ hl2.exe found  ({where})'
        else:
            msg = f'✖ no hl2.exe in {d}'
        self.dir_status.configure(text=msg, foreground=self.app.theme['ok' if ok else 'error'])
        maps = self.app.installed_maps(d)
        self.map_box.configure(values=[self.AUTO_MAP, self.NO_MAP] + maps)
        self.fallback_box.configure(values=maps)

    def browse(self):
        d = filedialog.askdirectory(parent=self, title='Folder that contains hl2.exe',
                                    initialdir=self.effective_dir() or os.path.expanduser('~'))
        if d:
            self.game_dir.set(os.path.normpath(d))

    def save(self):
        try:
            wait = max(0.0, float(self.wait.get()))
        except ValueError:
            messagebox.showwarning(APP_NAME, 'The wait must be a number of seconds.', parent=self)
            return
        st = self.app.settings
        st['game_dir'] = self.game_dir.get().strip()
        st['launch_options'] = self.options.get().strip() or tslang.DEFAULT_LAUNCH_OPTIONS
        m = self.map.get().strip()
        st['launch_map'] = {self.AUTO_MAP: '', self.NO_MAP: '-'}.get(m, m)
        st['fallback_map'] = self.fallback.get().strip()
        st['launch_wait_s'] = wait
        st['reuse_game'] = self.reuse.get()
        st['game_link'] = self.link.get()
        st['run_template'] = self.template.get().strip() or 'test_startscript {path}'
        st.save()
        self.app.set_status_message('Game settings saved')
        self.destroy()


class MapWindow(Dialog):
    """Browse the entities of the script's map; pick which map the script is for."""

    AUTO = '(auto - from the script folder)'
    NONE = '(no map)'

    def __init__(self, app, editor):
        super().__init__(app, 'Map entities')
        self.geometry('980x600')
        self.ed = editor
        b = self.body
        top = ttk.Frame(b)
        top.pack(fill='x')
        ttk.Label(top, text='Map for this script').pack(side='left')
        self.map_var = tk.StringVar()
        self.map_box = ttk.Combobox(top, textvariable=self.map_var, width=30, state='readonly')
        self.map_box.pack(side='left', padx=6)
        self.map_box.bind('<<ComboboxSelected>>', lambda e: self.choose_map())
        self.info = ttk.Label(top, text='')
        self.info.pack(side='left', padx=10)
        sf = ttk.Frame(b)
        sf.pack(fill='x', pady=(8, 0))
        ttk.Label(sf, text='Search').pack(side='left')
        self.q = tk.StringVar()
        qe = ttk.Entry(sf, textvariable=self.q)
        qe.pack(side='left', fill='x', expand=True, padx=6)
        self.named_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(sf, text='Named only', variable=self.named_only, command=self.fill).pack(side='left')

        tf = ttk.Frame(b)
        tf.pack(fill='both', expand=True, pady=(6, 0))
        cols = ('cls', 'hid', 'origin')
        self.tree = ttk.Treeview(tf, columns=cols, show='tree headings', selectmode='browse')
        for c, (title, w) in zip(('#0',) + cols, (('Name', 220), ('Class', 220), ('Hammer ID', 90), ('Origin', 220))):
            self.tree.heading(c, text=title, anchor='w')
            self.tree.column(c, width=w, stretch=c in ('#0', 'origin'))
        sb = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')
        self.tree.bind('<Double-1>', lambda e: self.insert('name'))
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.show_outputs())
        self.outputs = ttk.Label(b, text='', wraplength=940, justify='left')
        self.outputs.pack(fill='x', pady=(6, 0))
        bf = ttk.Frame(b)
        bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text='Insert name', command=lambda: self.insert('name')).pack(side='left')
        ttk.Button(bf, text='Insert hammerid', command=lambda: self.insert('hid')).pack(side='left', padx=6)
        ttk.Button(bf, text='Insert origin', command=lambda: self.insert('origin')).pack(side='left')
        ttk.Label(bf, text='Double-click inserts the name (or the hammerid when it has none)').pack(side='left', padx=12)
        ttk.Button(bf, text='Close', command=self.destroy).pack(side='right')
        self.q.trace_add('write', lambda *_: self.fill())
        self._rows = {}
        self.refresh_maps()
        self.center()
        qe.focus_set()

    def refresh_maps(self):
        maps = self.app.installed_maps(self.app.game_dir_for(self.ed.path or ''))
        self.map_box.configure(values=[self.AUTO, self.NONE] + maps)
        choice = self.app.script_map_choice(self.ed)
        self.map_var.set({None: self.AUTO, '': self.NONE}.get(choice, choice))
        self.fill()

    def choose_map(self):
        v = self.map_var.get()
        self.app.set_script_map(self.ed, {self.AUTO: None, self.NONE: ''}.get(v, v))
        self.fill()

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        mi = self.app.mapinfo_for(self.ed)
        if mi is None:
            why = 'save the script under tf\\testscripts and set the game folder' if not self.ed.path else \
                'no map picked for this script - choose one above'
            self.info.configure(text=why)
            return
        self.info.configure(text=f'{len(mi.entities)} entities, {len(mi.names)} named')
        q = self.q.get().lower()
        n = 0
        for e in sorted(mi.entities, key=lambda e: (not e.targetname, e.targetname.lower(), e.classname)):
            if self.named_only.get() and not e.targetname:
                continue
            if q and q not in e.targetname.lower() and q not in e.classname.lower() and q not in e.hammerid:
                continue
            iid = self.tree.insert('', 'end', text=e.targetname, values=(e.classname, e.hammerid, e.origin))
            self._rows[iid] = e
            n += 1
            if n >= 3000:
                break

    def selected(self):
        sel = self.tree.selection()
        return self._rows.get(sel[0]) if sel else None

    def show_outputs(self):
        e = self.selected()
        if not e or not e.outputs:
            self.outputs.configure(text='')
            return
        shown = '   '.join(f'{k} {v}' for k, v in e.outputs[:6])
        more = f'   (+{len(e.outputs) - 6} more)' if len(e.outputs) > 6 else ''
        self.outputs.configure(text=f'Outputs: {shown}{more}')

    def insert(self, what):
        e = self.selected()
        if not e:
            return
        if what == 'name':
            text = e.targetname or e.hammerid
        elif what == 'hid':
            text = e.hammerid
        else:
            text = e.origin
        if text:
            self.ed.text.insert('insert', text)
            self.ed.text.focus_set()


class ConsoleWindow(Dialog):
    """Live view of the game's console (tf/console.log) plus a command line sent over RCON."""

    def __init__(self, app):
        super().__init__(app, 'Game console')
        self.geometry('900x520')
        self.resizable(True, True)
        b = self.body
        self.out = tk.Text(b, wrap='word', font=app.font, state='disabled', **app.text_opts())
        sb = ttk.Scrollbar(b, orient='vertical', command=self.out.yview)
        self.out.configure(yscrollcommand=sb.set)
        self.out.grid(row=0, column=0, sticky='nsew')
        sb.grid(row=0, column=1, sticky='ns')
        t = app.theme
        self.out.tag_configure('cmd', foreground=t['accent'])
        self.out.tag_configure('reply', foreground=t['ok'])
        self.out.tag_configure('note', foreground=t['muted'])
        self.out.tag_configure('err', foreground=t['error'])
        row = ttk.Frame(b)
        row.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Label(row, text=']').pack(side='left')
        self.cmd = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.cmd, font=app.font)
        e.pack(side='left', fill='x', expand=True, padx=6)
        ttk.Button(row, text='Send', command=self.send).pack(side='left')
        ttk.Button(row, text='Clear', command=self.clear).pack(side='left', padx=(6, 0))
        b.rowconfigure(0, weight=1)
        b.columnconfigure(0, weight=1)
        e.bind('<Return>', lambda ev: self.send())
        e.bind('<Up>', lambda ev: self.history_step(-1))
        e.bind('<Down>', lambda ev: self.history_step(1))
        self.history, self.hpos = [], 0
        self.log_path = self.app.console_log_path()
        self.log_pos = None
        if self.log_path and os.path.isfile(self.log_path):
            self.log_pos = max(0, os.path.getsize(self.log_path) - 20000)   # show the recent tail
            self.write(f'Showing {self.log_path}\n', 'note')
        else:
            self.write('No console log yet - start TF2 with F9 so it writes tf\\console.log.\n'
                       'Commands typed below still work once the game is linked.\n', 'note')
        self.center()
        e.focus_set()
        self.poll()

    def write(self, text, tag=None):
        at_end = self.out.yview()[1] >= 0.999
        self.out.configure(state='normal')
        self.out.insert('end', text, tag or ())
        lines = int(self.out.index('end-1c').split('.')[0])
        if lines > 5000:
            self.out.delete('1.0', f'{lines - 5000}.0')
        self.out.configure(state='disabled')
        if at_end:
            self.out.see('end')

    def clear(self):
        self.out.configure(state='normal')
        self.out.delete('1.0', 'end')
        self.out.configure(state='disabled')

    def poll(self):
        if not self.winfo_exists():
            return
        path = self.app.console_log_path()
        if path and path != self.log_path:
            self.log_path, self.log_pos = path, 0
        if self.log_path and os.path.isfile(self.log_path):
            size = os.path.getsize(self.log_path)
            if self.log_pos is None or size < self.log_pos:
                self.log_pos = 0           # the game started a new log
            if size > self.log_pos:
                with open(self.log_path, 'rb') as f:
                    f.seek(self.log_pos)
                    data = f.read(size - self.log_pos)
                self.log_pos = size
                self.write(data.decode('utf-8', 'replace').replace('\r\n', '\n'))
        self.after(400, self.poll)

    def history_step(self, step):
        if not self.history:
            return 'break'
        self.hpos = max(0, min(len(self.history), self.hpos + step))
        self.cmd.set(self.history[self.hpos] if self.hpos < len(self.history) else '')
        return 'break'

    def send(self):
        cmd = self.cmd.get().strip()
        if not cmd:
            return
        self.history.append(cmd)
        self.hpos = len(self.history)
        self.cmd.set('')
        self.write(f'] {cmd}\n', 'cmd')
        try:
            reply = self.app.game_command(cmd)
        except rcon.RconError as e:
            self.write(f'{e}\n', 'err')
            return
        # output of RCON commands only comes back here, it isn't written to console.log
        if reply:
            self.write(reply if reply.endswith('\n') else reply + '\n', 'reply')


class FindDialog(Dialog):
    def __init__(self, app, replace=False):
        super().__init__(app, 'Find and replace' if replace else 'Find')
        self.resizable(False, False)
        b = self.body
        self.find = tk.StringVar(value=app.last_find)
        self.repl = tk.StringVar(value='')
        self.case = tk.BooleanVar(value=False)
        self.regex = tk.BooleanVar(value=False)
        self.word = tk.BooleanVar(value=False)
        ttk.Label(b, text='Find').grid(row=0, column=0, sticky='w')
        fe = ttk.Entry(b, textvariable=self.find, width=40)
        fe.grid(row=0, column=1, sticky='ew', padx=4)
        ttk.Label(b, text='Replace').grid(row=1, column=0, sticky='w')
        ttk.Entry(b, textvariable=self.repl, width=40).grid(row=1, column=1, sticky='ew', padx=4)
        of = ttk.Frame(b)
        of.grid(row=2, column=1, sticky='w', pady=4)
        ttk.Checkbutton(of, text='Match case', variable=self.case).pack(side='left')
        ttk.Checkbutton(of, text='Whole word', variable=self.word).pack(side='left', padx=6)
        ttk.Checkbutton(of, text='Regex', variable=self.regex).pack(side='left')
        bf = ttk.Frame(b)
        bf.grid(row=0, column=2, rowspan=4, sticky='n')
        for txt, cmd in (('Find next', lambda: self.search(1)), ('Find previous', lambda: self.search(-1)),
                         ('Replace', self.replace_one), ('Replace all', self.replace_all),
                         ('Close', self.destroy)):
            ttk.Button(bf, text=txt, command=cmd, width=14).pack(fill='x', pady=1)
        self.status = ttk.Label(b, text='')
        self.status.grid(row=3, column=0, columnspan=2, sticky='w')
        self.bind('<Return>', lambda e: self.search(1))
        self.bind('<Shift-Return>', lambda e: self.search(-1))
        self.bind('<Destroy>', lambda e: self._clear() if e.widget is self else None)
        self.center()
        fe.focus_set()
        fe.select_range(0, 'end')

    def pattern(self):
        s = self.find.get()
        if not s:
            return None
        p = s if self.regex.get() else re.escape(s)
        if self.word.get():
            p = r'(?<![\w!*@`^.\-])' + p + r'(?![\w])'
        try:
            return re.compile(p, 0 if self.case.get() else re.I)
        except re.error as e:
            self.status.configure(text=f'Bad regex: {e}')
            return None

    def _clear(self):
        ed = self.app.current()
        if ed:
            ed.text.tag_remove('found', '1.0', 'end')

    def _mark_all(self, ed, pat):
        t = ed.text
        t.tag_remove('found', '1.0', 'end')
        text = ed.get_text()
        matches = list(pat.finditer(text))
        for m in matches[:5000]:
            t.tag_add('found', f'1.0+{m.start()}c', f'1.0+{m.end()}c')
        return text, matches

    def search(self, direction):
        ed = self.app.current()
        pat = self.pattern()
        if not ed or not pat:
            return
        self.app.last_find = self.find.get()
        t = ed.text
        text, matches = self._mark_all(ed, pat)
        if not matches:
            self.status.configure(text='Not found')
            return
        pos = len(t.get('1.0', 'insert'))
        if direction > 0:
            nxt = next((m for m in matches if m.start() >= pos and m.end() != pos), None) or matches[0]
        else:
            sel_start = len(t.get('1.0', 'sel.first')) if t.tag_ranges('sel') else pos
            prev = [m for m in matches if m.start() < sel_start]
            nxt = prev[-1] if prev else matches[-1]
        t.tag_remove('sel', '1.0', 'end')
        s, e = f'1.0+{nxt.start()}c', f'1.0+{nxt.end()}c'
        t.tag_add('sel', s, e)
        t.mark_set('insert', e if direction > 0 else s)
        t.see(s)
        self.status.configure(text=f'{len(matches)} match(es)')

    def replace_one(self):
        ed = self.app.current()
        pat = self.pattern()
        if not ed or not pat:
            return
        t = ed.text
        if t.tag_ranges('sel'):
            sel = t.get('sel.first', 'sel.last')
            m = pat.fullmatch(sel)
            if m:
                rep = m.expand(self.repl.get()) if self.regex.get() else self.repl.get()
                start = t.index('sel.first')
                begin_undo(t)
                t.delete('sel.first', 'sel.last')
                t.insert(start, rep)
                end_undo(t)
                t.mark_set('insert', f'{start}+{len(rep)}c')
        self.search(1)

    def replace_all(self):
        ed = self.app.current()
        pat = self.pattern()
        if not ed or not pat:
            return
        text = ed.get_text()
        rep = self.repl.get()
        new, n = pat.subn(rep if self.regex.get() else (lambda m: rep), text)
        if n:
            self.app.replace_all_text(ed, new)
        self.status.configure(text=f'Replaced {n}')


class ReferenceWindow(Dialog):
    """Searchable list of every command, input, output, keyvalue and entity."""

    def __init__(self, app):
        super().__init__(app, 'Testscript language reference')
        self.geometry('820x560')
        b = self.body
        self.q = tk.StringVar()
        top = ttk.Frame(b)
        top.pack(fill='x')
        ttk.Label(top, text='Search').pack(side='left')
        e = ttk.Entry(top, textvariable=self.q)
        e.pack(side='left', fill='x', expand=True, padx=6)
        self.kind = tk.StringVar(value='All')
        ttk.Combobox(top, textvariable=self.kind, state='readonly', width=12,
                     values=['All', 'Commands', 'Inputs', 'Outputs', 'Keyvalues', 'Entities']).pack(side='left')
        self.tree = ttk.Treeview(b, columns=('kind', 'desc'), show='tree headings')
        self.tree.heading('#0', text='Name')
        self.tree.heading('kind', text='Kind')
        self.tree.heading('desc', text='Description')
        self.tree.column('#0', width=200)
        self.tree.column('kind', width=80, stretch=False)
        self.tree.column('desc', width=500)
        sb = ttk.Scrollbar(b, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True, pady=(6, 0))
        sb.pack(side='left', fill='y', pady=(6, 0))
        ttk.Label(self, text='Double-click to insert at the cursor', padding=(10, 4)).pack(anchor='w')
        self.q.trace_add('write', lambda *_: self.fill())
        self.kind.trace_add('write', lambda *_: self.fill())
        self.tree.bind('<Double-1>', self.insert)
        self.fill()
        e.focus_set()

    def fill(self):
        self.tree.delete(*self.tree.get_children())
        q = self.q.get().lower()
        groups = [('Commands', 'command', tslang.COMMANDS), ('Inputs', 'input', tslang.INPUTS),
                  ('Outputs', 'output', tslang.OUTPUTS), ('Keyvalues', 'keyvalue', tslang.KEYVALUES),
                  ('Entities', 'entity', tslang.ENTITIES)]
        for gname, kind, table in groups:
            if self.kind.get() not in ('All', gname):
                continue
            for name, desc in table.items():
                if q and q not in name.lower() and q not in desc.lower():
                    continue
                self.tree.insert('', 'end', text=name, values=(kind, desc))

    def insert(self, _event):
        sel = self.tree.selection()
        ed = self.app.current()
        if sel and ed:
            ed.text.insert('insert', self.tree.item(sel[0], 'text'))
            ed.text.focus_set()


# ==========================================================================
# Main window
# ==========================================================================

class App:
    def __init__(self, files):
        self.settings = Settings()
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry(self.settings['geometry'])
        self.root.minsize(700, 400)
        icon = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))),
                            'assets', 'icon.ico')
        try:
            if sys.platform == 'win32' and os.path.isfile(icon):
                self.root.iconbitmap(default=icon)     # also used by every dialog
            else:
                self.root.iconphoto(True, self._make_icon())
        except tk.TclError:
            pass
        self.last_find = ''
        self.find_dialog = None
        self.font = tkfont.Font(family=self.settings['font_family'], size=self.settings['font_size'])
        self.ui_font = tkfont.Font(family='Segoe UI', size=9)
        self.ui_bold = tkfont.Font(family='Segoe UI', size=8, weight='bold')
        self._styled = {}
        self.editors = []

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            pass
        self._build_ui()
        self._build_menu()
        self._bind_keys()
        self.apply_theme()

        opened = False
        for p in files:
            opened |= self.open_path(p)
        if not opened:
            for p in self.settings['open_files']:
                if os.path.isfile(p):
                    opened |= self.open_path(p)
        if not opened:
            self.new_file()
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.after(120, self._restore_sashes)

    def _make_icon(self):
        img = tk.PhotoImage(width=16, height=16)
        img.put('#1e1f22', to=(0, 0, 16, 16))
        img.put('#cf6a32', to=(1, 1, 15, 15))
        img.put('#ffffff', to=(4, 4, 12, 6))
        img.put('#ffffff', to=(7, 6, 9, 13))
        return img

    # -- fonts / theme ----------------------------------------------------
    @property
    def theme(self):
        return THEMES.get(self.settings['theme'], THEMES['dark'])

    def styled_font(self, style):
        if not style:
            return self.font
        if style not in self._styled:
            f = self.font.copy()
            f.configure(weight='bold' if 'bold' in style else 'normal',
                        slant='italic' if 'italic' in style else 'roman',
                        underline='underline' in style)
            self._styled[style] = f
        return self._styled[style]

    def _sync_styled_fonts(self):
        for style, f in self._styled.items():
            f.configure(family=self.font.cget('family'), size=self.font.cget('size'))

    def text_opts(self):
        t = self.theme
        return dict(bg=t['bg'], fg=t['fg'], insertbackground=t['cursor'], selectbackground=t['select'],
                    selectforeground=t['fg'], relief='flat', borderwidth=0, highlightthickness=1,
                    highlightbackground=t['border'], highlightcolor=t['accent'], padx=6, pady=4)

    def _paint_close_images(self):
        """Draw the little x used on editor tabs (normal / hover / pressed)."""
        t = self.theme
        for img, color in ((self._img_close, t['muted']), (self._img_close_hover, t['fg']),
                           (self._img_close_press, t['accent'])):
            img.blank()
            for i in range(2, 10):
                for d in (0, 1):
                    if i + d < 12:
                        img.put(color, (i + d, i))
                        img.put(color, (11 - i - d, i))

    def apply_theme(self):
        t = self.theme
        s = self.style
        ui = self.ui_font
        bg, panel, border, muted = t['bg'], t['panel_bg'], t['border'], t['muted']
        strip = t['gutter_bg']
        s.configure('.', background=panel, foreground=t['panel_fg'], fieldbackground=bg, font=ui,
                    bordercolor=border, lightcolor=panel, darkcolor=panel, troughcolor=strip,
                    selectbackground=t['select'], selectforeground=t['fg'], insertcolor=t['fg'],
                    focuscolor=panel, arrowcolor=muted)
        s.map('.', background=[('disabled', panel)], foreground=[('disabled', muted)])
        # tree views (outline, problems, reference)
        s.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        s.configure('Treeview', background=panel, foreground=t['panel_fg'], fieldbackground=panel,
                    borderwidth=0, rowheight=ui.metrics('linespace') + 7, font=ui)
        s.map('Treeview', background=[('selected', t['select'])], foreground=[('selected', t['fg'])])
        s.configure('Treeview.Heading', background=panel, foreground=muted, relief='flat',
                    borderwidth=0, bordercolor=panel, lightcolor=panel, darkcolor=panel, font=ui, padding=(6, 3))
        s.map('Treeview.Heading', background=[('active', t['hover'])])
        # editor tabs
        s.configure('Editor.TNotebook', background=strip, borderwidth=0, bordercolor=strip,
                    lightcolor=strip, darkcolor=strip, tabmargins=(0, 0, 0, 0))
        s.configure('Editor.TNotebook.Tab', background=strip, foreground=muted, padding=(14, 6, 8, 6),
                    borderwidth=0, bordercolor=strip, lightcolor=strip, darkcolor=strip, font=ui)
        s.map('Editor.TNotebook.Tab',
              background=[('selected', bg), ('active', t['hover'])],
              foreground=[('selected', t['fg']), ('active', t['panel_fg'])],
              lightcolor=[('selected', t['accent'])], bordercolor=[('selected', strip)],
              expand=[('selected', (0, 0, 0, 0))])
        self._paint_close_images()
        # scrollbars
        for orient in ('Vertical', 'Horizontal'):
            s.configure(f'{orient}.TScrollbar', background=t['scroll'], troughcolor=bg, bordercolor=bg,
                        lightcolor=t['scroll'], darkcolor=t['scroll'], arrowcolor=muted,
                        gripcount=0, arrowsize=11, relief='flat')
            s.map(f'{orient}.TScrollbar',
                  background=[('pressed', t['scroll_hover']), ('active', t['scroll_hover'])],
                  lightcolor=[('active', t['scroll_hover'])], darkcolor=[('active', t['scroll_hover'])])
        # panes / panels
        s.configure('TPanedwindow', background=border)
        s.configure('Sash', sashthickness=4, gripcount=0, background=border,
                    lightcolor=border, darkcolor=border, bordercolor=border)
        s.configure('Panel.TFrame', background=panel)
        s.configure('Header.TFrame', background=panel)
        s.configure('Header.TLabel', background=panel, foreground=muted, font=self.ui_bold, padding=(10, 6, 4, 6))
        s.configure('HeaderInfo.TLabel', background=panel, foreground=muted, font=ui, padding=(4, 6))
        # toolbar
        s.configure('Toolbar.TFrame', background=panel)
        s.configure('Tool.TButton', background=panel, foreground=t['panel_fg'], borderwidth=0, relief='flat',
                    padding=(9, 4), bordercolor=panel, lightcolor=panel, darkcolor=panel,
                    focusthickness=0, font=ui)
        s.map('Tool.TButton', background=[('pressed', t['select']), ('active', t['hover'])],
              lightcolor=[('active', t['hover'])], darkcolor=[('active', t['hover'])],
              bordercolor=[('active', t['hover'])])
        s.configure('Small.Tool.TButton', padding=(6, 1))
        # status bar
        s.configure('Status.TFrame', background=t['status_bg'])
        s.configure('Status.TLabel', background=t['status_bg'], foreground=t['status_fg'], padding=(10, 3), font=ui)
        # dialog widgets
        s.configure('TButton', background=t['hover'], foreground=t['panel_fg'], padding=(14, 5),
                    bordercolor=border, lightcolor=t['hover'], darkcolor=t['hover'], focusthickness=0)
        s.map('TButton', background=[('pressed', t['select']), ('active', t['scroll'])],
              lightcolor=[('active', t['scroll'])], darkcolor=[('active', t['scroll'])])
        for w in ('TEntry', 'TCombobox', 'TSpinbox'):
            s.configure(w, fieldbackground=bg, foreground=t['fg'], background=panel, bordercolor=border,
                        lightcolor=bg, darkcolor=bg, arrowcolor=muted, insertcolor=t['fg'], padding=4)
            s.map(w, bordercolor=[('focus', t['accent'])], fieldbackground=[('readonly', bg)],
                  foreground=[('readonly', t['fg'])])
        for w in ('TCheckbutton', 'TRadiobutton'):
            s.configure(w, background=panel, foreground=t['panel_fg'], indicatorbackground=bg,
                        indicatorforeground=t['fg'], upperbordercolor=border, lowerbordercolor=border)
            s.map(w, background=[('active', panel)], indicatorbackground=[('selected', t['accent'])])
        self.root.configure(bg=strip)
        self.root.option_add('*TCombobox*Listbox.background', panel)
        self.root.option_add('*TCombobox*Listbox.foreground', t['panel_fg'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', t['select'])
        self.root.option_add('*TCombobox*Listbox.font', ui)
        self.problems.tag_configure('error', foreground=t['error'])
        self.problems.tag_configure('warning', foreground=t['warning'])
        self.problems.tag_configure('info', foreground=t['info'])
        self.problems.tag_configure('ok', foreground=t['ok'])
        self.outline.tag_configure('group', foreground=muted, font=self.ui_bold)
        set_dark_titlebar(self.root, self.settings['theme'] == 'dark')
        for ed in self.editors:
            ed.apply_theme()

    def set_theme(self, name):
        self.settings['theme'] = name
        self.theme_var.set(name)
        self.apply_theme()
        # nudge the window so Windows repaints the title bar colour
        w, h = self.root.winfo_width(), self.root.winfo_height()
        self.root.geometry(f'{w + 1}x{h}')
        self.root.after(30, lambda: self.root.geometry(f'{w}x{h}'))

    def zoom(self, step):
        size = self.font.cget('size') + step if step else 11
        size = max(6, min(40, size))
        self.font.configure(size=size)
        self._sync_styled_fonts()
        self.settings['font_size'] = size
        for ed in self.editors:
            ed.apply_theme()

    # -- layout -----------------------------------------------------------
    def _build_ui(self):
        root = self.root
        self._create_tab_close_element()

        # status bar
        self.status = ttk.Frame(root, style='Status.TFrame')
        self.status.pack(side='bottom', fill='x')
        self.status_parts = {}
        # right-hand parts are packed first so a long help text can't squeeze them out
        for key in ('eol', 'pos', 'hid', 'map', 'game', 'counts'):
            lbl = ttk.Label(self.status, text='', style='Status.TLabel')
            lbl.pack(side='right')
            self.status_parts[key] = lbl
        self.status_help = ttk.Label(self.status, text='', style='Status.TLabel', anchor='w', width=1)
        self.status_help.pack(side='left', fill='x', expand=True)
        self.status_parts['counts'].bind('<Button-1>', lambda e: self.next_problem(1))
        Tooltip(self.status_parts['counts'], 'Errors / warnings / notes - click to go to the next one', self)
        Tooltip(self.status_parts['hid'], 'Next free hammerid (Ctrl+I inserts it)', self)
        self.status_parts['map'].bind('<Button-1>', lambda e: self.map_window())
        self.status_parts['game'].configure(text='game not linked')
        self.status_parts['game'].bind('<Button-1>', lambda e: self.link_game())
        Tooltip(self.status_parts['game'], 'Connection to TF2 (RCON) - click to connect to a running game', self)
        Tooltip(self.status_parts['map'], 'Map this script is checked against - click to browse or change it', self)

        # toolbar
        self.toolbar = ttk.Frame(root, style='Toolbar.TFrame', padding=(4, 2))
        tools = [
            ('New', self.new_file, 'New script (Ctrl+N)'),
            ('Open', self.open_dialog, 'Open a testscript (Ctrl+O)'),
            ('Save', self.save, 'Save (Ctrl+S)'),
            None,
            ('+ Entity', self.insert_entity, 'Build an entity block (Ctrl+E)'),
            ('+ Output', self.insert_output, 'Build an output (Ctrl+Shift+O)'),
            ('+ Wait', lambda: self.insert_snippet('Test_Wait .1;'), 'Insert Test_Wait .1 (Ctrl+T)'),
            ('+ Alias', self.insert_alias, 'Insert an alias'),
            None,
            ('+ Coords', self.coord_dialog, 'Turn getpos output into origin / setpos text (Ctrl+P)'),
            ('Map', lambda: self.map_window(), 'Browse the map\'s entities and pick the script\'s map (Ctrl+M)'),
            None,
            ('▶ Run', self.run_in_game, 'Save and run in TF2 (F9) - set the game folder under Tools > Game settings'),
            ('Check', self.check_now, 'Check the script for problems (F5)'),
            ('Find', lambda: self.show_find(False), 'Find (Ctrl+F)'),
            ('Rename', self.rename_symbol, 'Rename a name everywhere (F2)'),
            ('Reference', lambda: ReferenceWindow(self), 'Language reference (F1)'),
        ]
        for item in tools:
            if item is None:
                ttk.Separator(self.toolbar, orient='vertical').pack(side='left', fill='y', padx=6, pady=4)
                continue
            label, cmd, tip = item
            b = ttk.Button(self.toolbar, text=label, command=cmd, style='Tool.TButton', takefocus=False, width=0)
            b.pack(side='left', padx=1)
            Tooltip(b, tip, self)
        tb = ttk.Button(self.toolbar, text='Theme', style='Tool.TButton', takefocus=False, width=0,
                        command=lambda: self.set_theme('light' if self.settings['theme'] == 'dark' else 'dark'))
        tb.pack(side='right', padx=1)
        Tooltip(tb, 'Switch dark / light theme', self)
        if self.settings['show_toolbar']:
            self.toolbar.pack(side='top', fill='x')

        self.hpane = ttk.PanedWindow(root, orient='horizontal')
        self.hpane.pack(fill='both', expand=True)

        # outline panel
        self.outline_frame = ttk.Frame(self.hpane, style='Panel.TFrame')
        self._panel_header(self.outline_frame, 'OUTLINE', 'show_outline')
        body = ttk.Frame(self.outline_frame, style='Panel.TFrame')
        body.pack(fill='both', expand=True)
        self.outline = ttk.Treeview(body, show='tree', selectmode='browse')
        osb = ttk.Scrollbar(body, orient='vertical', command=self.outline.yview)
        self.outline.configure(yscrollcommand=osb.set)
        self.outline.pack(side='left', fill='both', expand=True, padx=(4, 0))
        osb.pack(side='left', fill='y')
        self.outline.bind('<<TreeviewSelect>>', self._outline_jump)
        self._outline_lines = {}
        self._outline_open = {'sections': True, 'aliases': True, 'names': False, 'ids': False}

        # editor tabs
        self.vpane = ttk.PanedWindow(self.hpane, orient='vertical')
        self.nb = ttk.Notebook(self.vpane, style='Editor.TNotebook')
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self._tab_changed())
        self.nb.bind('<Button-2>', self._middle_click_tab)
        self.nb.bind('<ButtonPress-1>', self._tab_press, add=True)
        self.nb.bind('<ButtonRelease-1>', self._tab_release, add=True)
        self._close_pressed = None

        # problems panel
        self.problems_frame = ttk.Frame(self.vpane, style='Panel.TFrame')
        hdr = self._panel_header(self.problems_frame, 'PROBLEMS', 'show_problems')
        self.problems_info = ttk.Label(hdr, text='', style='HeaderInfo.TLabel')
        self.problems_info.pack(side='left')
        body = ttk.Frame(self.problems_frame, style='Panel.TFrame')
        body.pack(fill='both', expand=True)
        self.problems = ttk.Treeview(body, columns=('line', 'msg'), show='headings', height=5)
        self.problems.heading('line', text='Line', anchor='e')
        self.problems.heading('msg', text='Message', anchor='w')
        self.problems.column('line', width=64, stretch=False, anchor='e')
        self.problems.column('msg', width=800)
        psb = ttk.Scrollbar(body, orient='vertical', command=self.problems.yview)
        self.problems.configure(yscrollcommand=psb.set)
        self.problems.pack(side='left', fill='both', expand=True, padx=(4, 0))
        psb.pack(side='left', fill='y')
        self.problems.bind('<<TreeviewSelect>>', self._problem_jump)
        self._problem_rows = {}

        self.vpane.add(self.nb, weight=5)
        self.hpane.add(self.vpane, weight=5)
        self._layout_panels()

    def _panel_header(self, parent, title, setting):
        hdr = ttk.Frame(parent, style='Header.TFrame')
        hdr.pack(side='top', fill='x')
        ttk.Label(hdr, text=title, style='Header.TLabel').pack(side='left')
        x = ttk.Button(hdr, text='×', width=2, style='Small.Tool.TButton', takefocus=False,
                       command=lambda: self.toggle_panel(setting))
        x.pack(side='right', padx=4)
        Tooltip(x, 'Hide panel (View menu brings it back)', self)
        return hdr

    def _create_tab_close_element(self):
        self._img_close = tk.PhotoImage(width=12, height=12)
        self._img_close_hover = tk.PhotoImage(width=12, height=12)
        self._img_close_press = tk.PhotoImage(width=12, height=12)
        s = self.style
        s.element_create('tabclose', 'image', self._img_close,
                         ('active', 'pressed', '!disabled', self._img_close_press),
                         ('active', '!disabled', self._img_close_hover),
                         border=8, sticky='')
        s.layout('Editor.TNotebook.Tab', [
            ('Notebook.tab', {'sticky': 'nswe', 'children': [
                ('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [
                    ('Notebook.label', {'side': 'left', 'sticky': ''}),
                    ('Notebook.tabclose', {'side': 'left', 'sticky': ''}),
                ]}),
            ]}),
        ])

    def _tab_press(self, event):
        if 'tabclose' in self.nb.identify(event.x, event.y):
            self._close_pressed = self.nb.index(f'@{event.x},{event.y}')
            self.nb.state(['pressed'])
            return 'break'
        return None

    def _tab_release(self, event):
        if self._close_pressed is None:
            return None
        pressed, self._close_pressed = self._close_pressed, None
        self.nb.state(['!pressed'])
        if 'tabclose' not in self.nb.identify(event.x, event.y):
            return None
        try:
            idx = self.nb.index(f'@{event.x},{event.y}')
        except tk.TclError:
            return None
        if idx == pressed:
            self.close_editor(self.nb.nametowidget(self.nb.tabs()[idx]))
        return 'break'

    def _layout_panels(self):
        panes = self.hpane.panes()
        if self.settings['show_outline']:
            if str(self.outline_frame) not in map(str, panes):
                self.hpane.insert(0, self.outline_frame, weight=0)
        elif str(self.outline_frame) in map(str, panes):
            self.hpane.forget(self.outline_frame)
        vp = list(map(str, self.vpane.panes()))
        if self.settings['show_problems']:
            if str(self.problems_frame) not in vp:
                self.vpane.add(self.problems_frame, weight=0)
        elif str(self.problems_frame) in vp:
            self.vpane.forget(self.problems_frame)
        if hasattr(self, 'outline_var'):
            self.outline_var.set(self.settings['show_outline'])
            self.problems_var.set(self.settings['show_problems'])
        self._sash_pending = True
        self.root.after(30, self._restore_sashes)

    def _restore_sashes(self):
        """Put the panel dividers at the remembered sizes."""
        self._sash_pending = False
        try:
            self.root.update_idletasks()
            if self.settings['show_outline'] and len(self.hpane.panes()) > 1:
                self.hpane.sashpos(0, max(120, int(self.settings['outline_width'])))
            if self.settings['show_problems'] and len(self.vpane.panes()) > 1:
                h = self.vpane.winfo_height()
                if h > 200:
                    self.vpane.sashpos(0, h - max(80, int(self.settings['problems_height'])))
        except (tk.TclError, ValueError):
            pass

    def _remember_sashes(self):
        if getattr(self, '_sash_pending', False):
            return      # panes were just re-added and haven't been sized yet
        try:
            if self.settings['show_outline'] and len(self.hpane.panes()) > 1:
                self.settings['outline_width'] = self.hpane.sashpos(0)
            if self.settings['show_problems'] and len(self.vpane.panes()) > 1:
                self.settings['problems_height'] = self.vpane.winfo_height() - self.vpane.sashpos(0)
        except tk.TclError:
            pass

    def toggle_panel(self, key):
        self._remember_sashes()
        self.settings[key] = not self.settings[key]
        self._layout_panels()

    def toggle_toolbar(self):
        self.settings['show_toolbar'] = self.toolbar_var.get()
        if self.settings['show_toolbar']:
            self.toolbar.pack(side='top', fill='x', before=self.hpane)
        else:
            self.toolbar.pack_forget()

    def _build_menu(self):
        m = tk.Menu(self.root)
        self.root.configure(menu=m)

        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label='New', accelerator='Ctrl+N', command=self.new_file)
        tm = tk.Menu(fm, tearoff=False)
        for name in TEMPLATES:
            tm.add_command(label=name, command=lambda n=name: self.new_from_template(n))
        fm.add_cascade(label='New from template', menu=tm)
        fm.add_command(label='Open...', accelerator='Ctrl+O', command=self.open_dialog)
        self.recent_menu = tk.Menu(fm, tearoff=False, postcommand=self._fill_recent)
        fm.add_cascade(label='Open recent', menu=self.recent_menu)
        fm.add_command(label='Open testscripts folder', command=self.open_folder)
        fm.add_separator()
        fm.add_command(label='Save', accelerator='Ctrl+S', command=self.save)
        fm.add_command(label='Save as...', accelerator='Ctrl+Shift+S', command=self.save_as)
        fm.add_command(label='Save all', command=self.save_all)
        fm.add_separator()
        fm.add_command(label='Close tab', accelerator='Ctrl+W', command=self.close_current)
        fm.add_command(label='Exit', command=self.quit)
        m.add_cascade(label='File', menu=fm)

        em = tk.Menu(m, tearoff=False)
        em.add_command(label='Undo', accelerator='Ctrl+Z', command=lambda: self._text_event('<<Undo>>'))
        em.add_command(label='Redo', accelerator='Ctrl+Y', command=lambda: self._text_event('<<Redo>>'))
        em.add_separator()
        em.add_command(label='Cut', accelerator='Ctrl+X', command=lambda: self._text_event('<<Cut>>'))
        em.add_command(label='Copy', accelerator='Ctrl+C', command=lambda: self._text_event('<<Copy>>'))
        em.add_command(label='Paste', accelerator='Ctrl+V', command=lambda: self._text_event('<<Paste>>'))
        em.add_command(label='Select all', accelerator='Ctrl+A', command=self.select_all)
        em.add_separator()
        em.add_command(label='Find...', accelerator='Ctrl+F', command=lambda: self.show_find(False))
        em.add_command(label='Replace...', accelerator='Ctrl+H', command=lambda: self.show_find(True))
        em.add_command(label='Find next', accelerator='F3', command=lambda: self.find_again(1))
        em.add_command(label='Go to line...', accelerator='Ctrl+G', command=self.goto_dialog)
        em.add_separator()
        em.add_command(label='Toggle comment', accelerator='Ctrl+/', command=lambda: self._ed('toggle_comment'))
        em.add_command(label='Duplicate line', accelerator='Ctrl+D', command=lambda: self._ed('duplicate_line'))
        em.add_command(label='Move line up', accelerator='Alt+Up', command=lambda: self._ed('move_lines', -1))
        em.add_command(label='Move line down', accelerator='Alt+Down', command=lambda: self._ed('move_lines', 1))
        em.add_command(label='Autocomplete', accelerator='Ctrl+Space',
                       command=lambda: self.current() and self.current().complete(force=True))
        m.add_cascade(label='Edit', menu=em)

        im = tk.Menu(m, tearoff=False)
        im.add_command(label='Entity...', accelerator='Ctrl+E', command=self.insert_entity)
        im.add_command(label='Output...', accelerator='Ctrl+Shift+O', command=self.insert_output)
        im.add_command(label='Alias...', command=self.insert_alias)
        im.add_separator()
        im.add_command(label='Test_Wait .1', accelerator='Ctrl+T', command=lambda: self.insert_snippet('Test_Wait .1;'))
        im.add_command(label='Next free hammerid', accelerator='Ctrl+I', command=self.insert_hammerid)
        im.add_command(label='Start position (noclip/setpos/setang)',
                       command=lambda: self.insert_snippet('noclip;setpos 0 0 0;setang 90 90;'))
        im.add_command(label='Point client command (pcc)',
                       command=lambda: self.insert_snippet('give point_clientcommand;ent_fire point_clientcommand addoutput"targetname pcc;'))
        im.add_command(label='Point server command (psc)',
                       command=lambda: self.insert_snippet('give point_servercommand;ent_fire point_servercommand addoutput"targetname psc;'))
        im.add_command(label='Respawn times / goal text',
                       command=lambda: self.insert_snippet(
                           'ent_fire tf_gamerules setblueteamrespawnwavetime 5;\n'
                           'ent_fire tf_gamerules setredteamrespawnwavetime 5;\n'
                           'ent_fire tf_gamerules setblueteamgoalstring"Your goal here;\n'
                           'ent_fire tf_gamerules setredteamgoalstring"Your goal here;'))
        im.add_command(label='Restart round', command=lambda: self.insert_snippet('mp_restartround 1;'))
        im.add_command(label='End of script  ///', command=lambda: self.insert_snippet('///'))
        im.add_command(label='Section comment', command=lambda: self.insert_snippet('// ---- Section ----'))
        m.add_cascade(label='Insert', menu=im)

        tl = tk.Menu(m, tearoff=False)
        tl.add_command(label='Check script', accelerator='F5', command=self.check_now)
        tl.add_command(label='Next problem', accelerator='F8', command=lambda: self.next_problem(1))
        tl.add_command(label='Previous problem', accelerator='Shift+F8', command=lambda: self.next_problem(-1))
        tl.add_separator()
        tl.add_command(label='Run in game', accelerator='F9', command=self.run_in_game)
        tl.add_command(label='Copy run command', accelerator='Ctrl+F9', command=self.copy_run_command)
        tl.add_command(label='Game settings...', command=self.game_settings)
        tl.add_command(label='Game console', accelerator='Ctrl+`', command=self.console_window)
        tl.add_command(label='Position from game', accelerator='Ctrl+Shift+P', command=self.position_from_game)
        tl.add_command(label='Connect to running game', command=self.link_game)
        tl.add_separator()
        tl.add_command(label='Map entities...', accelerator='Ctrl+M', command=self.map_window)
        tl.add_command(label='Coordinates...', accelerator='Ctrl+P', command=self.coord_dialog)
        tl.add_command(label='Number +1', accelerator='Ctrl+Alt+Up', command=lambda: self._ed('nudge', 1))
        tl.add_command(label='Number -1', accelerator='Ctrl+Alt+Down', command=lambda: self._ed('nudge', -1))
        tl.add_command(label='Number +10 / -10', accelerator='Ctrl+Alt+Shift+Up/Down',
                       command=lambda: self._ed('nudge', 10))
        tl.add_separator()
        tl.add_command(label='Rename name everywhere...', accelerator='F2', command=self.rename_symbol)
        tl.add_command(label='Split commands onto separate lines', command=self.split_lines)
        tl.add_command(label='Join selected lines into one', command=self.join_lines)
        tl.add_command(label='Expand aliases into new tab', command=self.expand_aliases)
        tl.add_command(label='Remove comments into new tab', command=self.strip_comments)
        m.add_cascade(label='Tools', menu=tl)

        vm = tk.Menu(m, tearoff=False)
        self.theme_var = tk.StringVar(value=self.settings['theme'])
        vm.add_radiobutton(label='Dark theme', value='dark', variable=self.theme_var, command=lambda: self.set_theme('dark'))
        vm.add_radiobutton(label='Light theme', value='light', variable=self.theme_var, command=lambda: self.set_theme('light'))
        vm.add_separator()
        self.outline_var = tk.BooleanVar(value=self.settings['show_outline'])
        self.problems_var = tk.BooleanVar(value=self.settings['show_problems'])
        self.wrap_var = tk.BooleanVar(value=self.settings['wrap'])
        self.ac_var = tk.BooleanVar(value=self.settings['autocomplete'])
        self.toolbar_var = tk.BooleanVar(value=self.settings['show_toolbar'])
        vm.add_checkbutton(label='Toolbar', variable=self.toolbar_var, command=self.toggle_toolbar)
        vm.add_checkbutton(label='Outline panel', variable=self.outline_var, command=lambda: self.toggle_panel('show_outline'))
        vm.add_checkbutton(label='Problems panel', variable=self.problems_var, command=lambda: self.toggle_panel('show_problems'))
        vm.add_checkbutton(label='Word wrap', variable=self.wrap_var, command=self.toggle_wrap)
        vm.add_checkbutton(label='Autocomplete while typing', variable=self.ac_var, command=self.toggle_ac)
        vm.add_separator()
        vm.add_command(label='Zoom in', accelerator='Ctrl++', command=lambda: self.zoom(1))
        vm.add_command(label='Zoom out', accelerator='Ctrl+-', command=lambda: self.zoom(-1))
        vm.add_command(label='Reset zoom', accelerator='Ctrl+0', command=lambda: self.zoom(0))
        m.add_cascade(label='View', menu=vm)

        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label='Language reference', accelerator='F1', command=lambda: ReferenceWindow(self))
        hm.add_command(label='Keyboard shortcuts', command=self.show_shortcuts)
        hm.add_command(label='About', command=lambda: messagebox.showinfo(
            APP_NAME, f'{APP_NAME} {VERSION}\nAn editor for Orange Box / TF2 testscripts.', parent=self.root))
        m.add_cascade(label='Help', menu=hm)

    def _bind_keys(self):
        r = self.root
        self.shortcuts = binds = {
            '<Control-n>': self.new_file, '<Control-o>': self.open_dialog, '<Control-s>': self.save,
            '<Control-S>': self.save_as, '<Control-w>': self.close_current,
            '<Control-f>': lambda: self.show_find(False), '<Control-h>': lambda: self.show_find(True),
            '<F3>': lambda: self.find_again(1), '<Shift-F3>': lambda: self.find_again(-1),
            '<Control-g>': self.goto_dialog, '<Control-e>': self.insert_entity,
            '<Control-O>': self.insert_output, '<Control-t>': lambda: self.insert_snippet('Test_Wait .1;'),
            '<Control-i>': self.insert_hammerid, '<F5>': self.check_now,
            '<F8>': lambda: self.next_problem(1), '<Shift-F8>': lambda: self.next_problem(-1),
            '<F2>': self.rename_symbol, '<F1>': lambda: ReferenceWindow(self),
            '<F9>': self.run_in_game, '<Control-F9>': self.copy_run_command,
            '<Control-p>': self.coord_dialog, '<Control-m>': self.map_window,
            '<Control-grave>': self.console_window, '<Control-P>': self.position_from_game,
            '<Control-equal>': lambda: self.zoom(1), '<Control-plus>': lambda: self.zoom(1),
            '<Control-minus>': lambda: self.zoom(-1), '<Control-0>': lambda: self.zoom(0),
            '<Control-Tab>': lambda: self.cycle_tab(1), '<Control-Shift-Tab>': lambda: self.cycle_tab(-1),
        }
        for seq, fn in binds.items():
            r.bind_all(seq, lambda e, fn=fn: (fn(), 'break')[1])
        r.bind_class('Text', '<Control-a>', lambda e: (e.widget.tag_add('sel', '1.0', 'end-1c'), 'break')[1])

    def _bind_editor_keys(self, ed):
        t = ed.text
        t.bind('<Control-slash>', lambda e: ed.toggle_comment())
        t.bind('<Control-d>', lambda e: ed.duplicate_line())
        t.bind('<Alt-Up>', lambda e: ed.move_lines(-1))
        t.bind('<Alt-Down>', lambda e: ed.move_lines(1))
        t.bind('<Control-Alt-Up>', lambda e: ed.nudge(1))
        t.bind('<Control-Alt-Down>', lambda e: ed.nudge(-1))
        t.bind('<Control-Alt-Shift-Up>', lambda e: ed.nudge(10))
        t.bind('<Control-Alt-Shift-Down>', lambda e: ed.nudge(-10))
        # widget-level copies of the app shortcuts so Text's own bindings
        # (Ctrl+O open line, Ctrl+T transpose, Ctrl+H backspace...) don't run first
        for seq, fn in self.shortcuts.items():
            t.bind(seq, lambda e, fn=fn: (fn(), 'break')[1])
        t.bind('<Button-3>', lambda e: self._context_menu(e, ed))

    def _context_menu(self, event, ed):
        m = tk.Menu(self.root, tearoff=False)
        for label, ev in (('Cut', '<<Cut>>'), ('Copy', '<<Copy>>'), ('Paste', '<<Paste>>')):
            m.add_command(label=label, command=lambda ev=ev: ed.text.event_generate(ev))
        m.add_separator()
        m.add_command(label='Toggle comment', command=ed.toggle_comment)
        m.add_command(label='Rename name everywhere...', command=self.rename_symbol)
        m.add_command(label='Insert entity...', command=self.insert_entity)
        m.add_command(label='Insert output...', command=self.insert_output)
        m.tk_popup(event.x_root, event.y_root)

    # -- tabs -------------------------------------------------------------
    def current(self):
        try:
            w = self.nb.nametowidget(self.nb.select())
        except (tk.TclError, KeyError):
            return None
        return w if isinstance(w, Editor) else None

    def add_editor(self, path=None, content='', encoding='utf-8', newline='\r\n'):
        ed = Editor(self.nb, self, path, content, encoding, newline)
        self.editors.append(ed)
        self.nb.add(ed, text=ed.title)
        self.nb.select(ed)
        self._bind_editor_keys(ed)
        ed.text.focus_set()
        ed.text.mark_set('insert', '1.0')
        return ed

    def update_tab_title(self, ed):
        try:
            self.nb.tab(ed, text=('● ' if ed.modified else '') + ed.title)
        except tk.TclError:
            pass
        if ed is self.current():
            self._update_title()

    def _update_title(self):
        ed = self.current()
        if ed:
            where = ed.path or 'Untitled'
            self.root.title(f"{'* ' if ed.modified else ''}{where} - {APP_NAME}")
        else:
            self.root.title(APP_NAME)

    def _tab_changed(self):
        ed = self.current()
        self._update_title()
        if ed:
            ed.text.focus_set()
            self.on_analysis(ed)
            self.update_status(ed)

    def cycle_tab(self, step):
        tabs = self.nb.tabs()
        if tabs:
            i = (tabs.index(self.nb.select()) + step) % len(tabs)
            self.nb.select(tabs[i])

    def _middle_click_tab(self, event):
        try:
            idx = self.nb.index(f'@{event.x},{event.y}')
        except tk.TclError:
            return
        self.close_editor(self.nb.nametowidget(self.nb.tabs()[idx]))

    # -- files ------------------------------------------------------------
    def new_file(self):
        self.add_editor(content='')

    def new_from_template(self, name):
        title = simpledialog.askstring(APP_NAME, 'Gamemode / script name:', parent=self.root,
                                       initialvalue='My Gamemode')
        if title is None:
            return
        self.add_editor(content=TEMPLATES[name].replace('{name}', title))

    def open_dialog(self):
        paths = filedialog.askopenfilenames(parent=self.root, title='Open testscript',
                                            initialdir=self._initial_dir(), filetypes=FILETYPES)
        for p in paths:
            self.open_path(p)

    def _initial_dir(self):
        ed = self.current()
        if ed and ed.path:
            return os.path.dirname(ed.path)
        for d in (self.settings['last_dir'], DEFAULT_DIR):
            if d and os.path.isdir(d):
                return d
        return os.path.expanduser('~')

    def open_path(self, path):
        path = os.path.abspath(path)
        for ed in self.editors:
            if ed.path and os.path.normcase(ed.path) == os.path.normcase(path):
                self.nb.select(ed)
                return True
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError as e:
            messagebox.showerror(APP_NAME, f'Could not open {path}\n\n{e}', parent=self.root)
            return False
        if data.startswith(b'\xef\xbb\xbf'):
            enc = 'utf-8-sig'
        else:
            try:
                data.decode('utf-8')
                enc = 'utf-8'
            except UnicodeDecodeError:
                enc = 'cp1252'
        text = data.decode(enc, errors='replace')
        newline = '\r\n' if '\r\n' in text or '\n' not in text else '\n'
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        cur = self.current()
        blank = cur if cur and not cur.path and not cur.modified and not cur.get_text() else None
        self.add_editor(path, text, enc, newline)
        if blank is not None:
            self.close_editor(blank, ask=False)
        self._remember(path)
        return True

    def _remember(self, path):
        rec = [p for p in self.settings['recent'] if os.path.normcase(p) != os.path.normcase(path)]
        self.settings['recent'] = [path] + rec[:14]
        self.settings['last_dir'] = os.path.dirname(path)

    def _fill_recent(self):
        m = self.recent_menu
        m.delete(0, 'end')
        if not self.settings['recent']:
            m.add_command(label='(empty)', state='disabled')
        for p in self.settings['recent']:
            m.add_command(label=p, command=lambda p=p: self.open_path(p))

    def open_folder(self):
        d = self._initial_dir()
        try:
            os.startfile(d)
        except (OSError, AttributeError) as e:
            messagebox.showerror(APP_NAME, str(e), parent=self.root)

    def save(self, ed=None):
        ed = ed or self.current()
        if not ed:
            return False
        if not ed.path:
            return self.save_as(ed)
        return self._write(ed, ed.path)

    def save_as(self, ed=None):
        ed = ed or self.current()
        if not ed:
            return False
        path = filedialog.asksaveasfilename(parent=self.root, title='Save testscript as',
                                            initialdir=self._initial_dir(),
                                            initialfile=ed.title if ed.path else 'MyScript.txt',
                                            defaultextension='.txt', filetypes=FILETYPES)
        if not path:
            return False
        ed.path = os.path.abspath(path)
        ok = self._write(ed, ed.path)
        self._remember(ed.path)
        return ok

    def _write(self, ed, path):
        text = ed.get_text().replace('\n', ed.newline)
        try:
            with open(path, 'w', encoding=ed.encoding, newline='') as f:
                f.write(text)
        except (OSError, UnicodeEncodeError) as e:
            messagebox.showerror(APP_NAME, f'Could not save {path}\n\n{e}', parent=self.root)
            return False
        ed.set_saved()
        self.set_status_message(f'Saved {path}')
        return True

    def save_all(self):
        for ed in self.editors:
            if ed.modified:
                self.save(ed)

    def close_current(self):
        ed = self.current()
        if ed:
            self.close_editor(ed)

    def close_editor(self, ed, ask=True):
        if ask and ed.modified:
            self.nb.select(ed)
            r = messagebox.askyesnocancel(APP_NAME, f'Save changes to {ed.title}?', parent=self.root)
            if r is None:
                return False
            if r and not self.save(ed):
                return False
        ed.completer.hide()
        self.nb.forget(ed)
        self.editors.remove(ed)
        ed.destroy()
        if not self.editors:
            self.new_file()
        return True

    def quit(self):
        for ed in list(self.editors):
            if ed.modified:
                self.nb.select(ed)
                r = messagebox.askyesnocancel(APP_NAME, f'Save changes to {ed.title}?', parent=self.root)
                if r is None:
                    return
                if r and not self.save(ed):
                    return
        self.settings['open_files'] = [ed.path for ed in self.editors if ed.path]
        self.settings['geometry'] = self.root.geometry()
        self._remember_sashes()
        self.settings.save()
        self.root.destroy()

    # -- edit helpers -----------------------------------------------------
    def _text_event(self, ev):
        ed = self.current()
        if ed:
            ed.text.event_generate(ev)

    def _ed(self, method, *args):
        ed = self.current()
        if ed:
            getattr(ed, method)(*args)

    def select_all(self):
        ed = self.current()
        if ed:
            ed.text.tag_add('sel', '1.0', 'end-1c')

    def show_find(self, replace):
        ed = self.current()
        if ed and ed.text.tag_ranges('sel'):
            sel = ed.text.get('sel.first', 'sel.last')
            if '\n' not in sel:
                self.last_find = sel
        if self.find_dialog is not None and self.find_dialog.winfo_exists():
            self.find_dialog.destroy()
        self.find_dialog = FindDialog(self, replace)

    def find_again(self, direction):
        if self.find_dialog is not None and self.find_dialog.winfo_exists():
            self.find_dialog.search(direction)
        else:
            self.show_find(False)

    def goto_dialog(self):
        ed = self.current()
        if not ed:
            return
        n = simpledialog.askinteger(APP_NAME, f'Go to line (1-{ed.line_count()}):', parent=self.root,
                                    minvalue=1, maxvalue=ed.line_count())
        if n:
            ed.goto_line(n)

    def replace_all_text(self, ed, new):
        t = ed.text
        top = t.yview()[0]
        pos = t.index('insert')
        begin_undo(t)
        t.delete('1.0', 'end')
        t.insert('1.0', new)
        end_undo(t)
        t.mark_set('insert', pos)
        t.yview_moveto(top)

    def insert_block(self, ed, code):
        """Insert code as whole lines after the cursor's line (or on it if empty)."""
        t = ed.text
        line = t.get('insert linestart', 'insert lineend')
        begin_undo(t)
        if line.strip():
            t.mark_set('insert', 'insert lineend')
            t.insert('insert', '\n' + code)
        else:
            t.delete('insert linestart', 'insert lineend')
            t.insert('insert', code)
        end_undo(t)
        t.see('insert')
        t.focus_set()

    def insert_snippet(self, code):
        ed = self.current()
        if ed:
            self.insert_block(ed, code)

    def insert_entity(self):
        ed = self.current()
        if ed:
            ed._run_analysis()
            EntityDialog(self, ed)

    def insert_output(self):
        ed = self.current()
        if ed:
            ed._run_analysis()
            OutputDialog(self, ed)

    def insert_alias(self):
        ed = self.current()
        if not ed:
            return
        used = set(ed.analysis.aliases)
        free = next((c for c in 'abcdefghijklmnopqrstuvwxyz' if c not in used), 'x')
        name = simpledialog.askstring(APP_NAME, 'Alias name:', initialvalue=free, parent=self.root)
        if not name:
            return
        body = simpledialog.askstring(APP_NAME, f'Command for alias {name}\n(one command - ";" ends it):',
                                      initialvalue='give logic_relay', parent=self.root)
        if body is None:
            return
        self.insert_block(ed, f'alias {name}"{body.strip().rstrip(";")};')

    def coord_dialog(self):
        ed = self.current()
        if ed:
            ed._run_analysis()
            CoordDialog(self, ed)

    def _script_to_run(self):
        """Save the current script and return (editor, path from testscripts), or None."""
        ed = self.current()
        if not ed:
            return None
        ed._run_analysis()
        if ed.analysis.end_line is None and ed.get_text().strip():
            add = messagebox.askyesnocancel(
                APP_NAME, "This script doesn't end with '///', so its last lines won't run correctly.\n\n"
                          "Add '///' at the end now?", parent=self.root)
            if add is None:
                return None
            if add:
                t = ed.text
                begin_undo(t)
                t.insert('end-1c', ('' if ed.get_text().endswith('\n') else '\n') + '///\n')
                end_undo(t)
                ed._run_analysis()
        if (ed.modified or not ed.path) and not self.save(ed):
            return None
        rel = tslang.testscript_relpath(ed.path)
        if rel is None:
            messagebox.showwarning(
                APP_NAME, f'{ed.path}\n\nis not inside a testscripts folder, so the game can\'t find it.\n'
                          'Save it under ...\\tf\\testscripts\\ and try again.', parent=self.root)
            return None
        return ed, rel

    def copy_run_command(self):
        got = self._script_to_run()
        if not got:
            return
        cmd = tslang.run_command(got[0].path, self.settings['run_template'])
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        self.set_status_message(f'Copied  {cmd}  - paste it into the TF2 console')

    def _map_key(self, ed):
        return os.path.normcase(os.path.abspath(ed.path)) if ed.path else None

    def script_map_choice(self, ed):
        """The map picked for this script: a map name, '' for none, or None for automatic."""
        key = self._map_key(ed)
        return self.settings['script_maps'].get(key) if key else None

    def set_script_map(self, ed, choice):
        key = self._map_key(ed)
        if not key:
            return
        maps = dict(self.settings['script_maps'])
        if choice is None:
            maps.pop(key, None)
        else:
            maps[key] = choice
        self.settings['script_maps'] = maps
        ed._run_analysis()

    def mapinfo_for(self, ed):
        """MapInfo for the script's map (picked, or guessed from its folder), or None."""
        if not ed.path:
            return None
        game_dir = self.game_dir_for(ed.path)
        choice = self.script_map_choice(ed)
        if choice is None:
            rel = tslang.testscript_relpath(ed.path)
            choice = tslang.guess_map(rel, self.installed_maps(game_dir)) if rel else None
        return mapdata.load_map(game_dir, choice) if choice else None

    def map_window(self):
        ed = self.current()
        if ed:
            MapWindow(self, ed)

    def game_dir_for(self, path):
        return self.settings['game_dir'].strip() or tslang.game_dir_from_script(path) or ''

    @staticmethod
    def installed_maps(game_dir):
        folder = os.path.join(game_dir, 'tf', 'maps') if game_dir else ''
        try:
            return sorted(f[:-4] for f in os.listdir(folder) if f.lower().endswith('.bsp'))
        except OSError:
            return []

    @staticmethod
    def game_running():
        if sys.platform != 'win32':
            return False
        try:
            out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq hl2.exe', '/NH'], capture_output=True,
                                 text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return 'hl2.exe' in out.lower()

    def run_in_game(self):
        """Save the script and start it in TF2 (launching the game when it isn't running)."""
        got = self._script_to_run()
        if not got:
            return
        ed, rel = got
        st = self.settings
        cmd = tslang.run_command(ed.path, st['run_template'])
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        game_dir = self.game_dir_for(ed.path)
        hl2 = os.path.join(game_dir, 'hl2.exe') if game_dir else ''
        if not hl2 or not os.path.isfile(hl2):
            self.set_status_message(f'Copied  {cmd}  - set the game folder to launch TF2 from here')
            GameSettingsDialog(self, ed.path)
            return

        if st['reuse_game'] and self.game_running():
            if st['game_link']:
                try:
                    self.game_command(cmd)
                    self.set_status_message(f'Ran {rel} in TF2 over the game link   (also copied: {cmd})')
                    return
                except rcon.RconError:
                    pass        # e.g. started from client.bat without -usercon: fall back to -hijack
            args = f'"{hl2}" -hijack -game tf +{cmd}'
            what = 'Sent to the running game'
        else:
            map_name = None
            if st['launch_map'] == '':
                choice = self.script_map_choice(ed)
                if choice is None:
                    choice = tslang.guess_map(rel, self.installed_maps(game_dir))
                map_name = choice or st['fallback_map'] or None
            elif st['launch_map'] != '-':
                map_name = st['launch_map']
            if map_name:
                launcher = os.path.join(game_dir, 'tf', 'testscripts', tslang.LAUNCHER_SCRIPT)
                try:
                    with open(launcher, 'w', encoding='utf-8', newline='\r\n') as f:
                        f.write(tslang.launcher_script(rel, map_name, st['launch_wait_s']))
                except OSError as e:
                    messagebox.showerror(APP_NAME, f'Could not write {launcher}\n\n{e}', parent=self.root)
                    return
                script_arg = tslang.LAUNCHER_SCRIPT
                what = f'Launching TF2 on {map_name}, then {rel}'
            else:
                script_arg = rel
                what = f'Launching TF2 with {rel}'
            options = tslang.launch_options(st['launch_options'])
            if st['game_link']:
                options = gamelink.link_options(options, self.rcon_password())
            args = f'"{hl2}" {options} -testscript "{script_arg}"'
        try:
            subprocess.Popen(args, cwd=game_dir)
        except OSError as e:
            messagebox.showerror(APP_NAME, f'Could not start the game\n\n{args}\n\n{e}', parent=self.root)
            return
        self.set_status_message(f'{what}   (also copied: {cmd})')

    def game_settings(self):
        ed = self.current()
        GameSettingsDialog(self, ed.path if ed else None)

    # -- game link (RCON) -------------------------------------------------
    def rcon_password(self):
        if not self.settings['rcon_password']:
            self.settings['rcon_password'] = secrets.token_hex(8)
            self.settings.save()
        return self.settings['rcon_password']

    def game_command(self, cmd):
        """Run a console command in the running TF2 and return its output (raises rcon.RconError)."""
        port = gamelink.port_from_options(self.settings['launch_options'])
        link = getattr(self, 'link', None)
        if link is None or link.port != port or link.password != self.rcon_password():
            if link is not None:
                link.close()
            link = self.link = gamelink.GameLink(self.rcon_password(), port)
        try:
            out = link.command(cmd)
        except rcon.RconError:
            self._set_link_status(False)
            raise
        self._set_link_status(True)
        return out

    def _set_link_status(self, ok):
        lbl = self.status_parts.get('game')
        if lbl is not None:
            lbl.configure(text='game linked' if ok else 'game not linked')

    def link_game(self):
        try:
            out = self.game_command('status')
            m = re.search(r'map\s*:\s*(\S+)', out)
            self.set_status_message(f"Linked to TF2{' on ' + m.group(1) if m else ''}")
        except rcon.RconError as e:
            self.set_status_message(f'Game link: {e}')

    def console_log_path(self):
        ed = self.current()
        game_dir = self.game_dir_for(ed.path) if ed and ed.path else self.settings['game_dir'].strip()
        return os.path.join(game_dir, 'tf', 'console.log') if game_dir else None

    def console_window(self):
        if getattr(self, '_console', None) is not None and self._console.winfo_exists():
            self._console.lift()
            return
        self._console = ConsoleWindow(self)

    def position_from_game(self):
        ed = self.current()
        if ed:
            ed._run_analysis()
            d = CoordDialog(self, ed)
            d.from_game()

    def insert_hammerid(self):
        ed = self.current()
        if ed:
            ed._run_analysis()
            ed.text.insert('insert', str(ed.analysis.next_hammerid()))

    # -- tools ------------------------------------------------------------
    def check_now(self):
        ed = self.current()
        if not ed:
            return
        ed._run_analysis()
        counts = {'error': 0, 'warning': 0, 'info': 0}
        for d in ed.analysis.diagnostics:
            counts[d.severity] += 1
        if not self.settings['show_problems']:
            self.problems_var.set(True)
            self.toggle_panel('show_problems')
        self.set_status_message(f"Check: {counts['error']} errors, {counts['warning']} warnings, {counts['info']} notes")

    def next_problem(self, direction):
        ed = self.current()
        if not ed or not ed.analysis.diagnostics:
            return
        ln = int(ed.text.index('insert').split('.')[0])
        ds = ed.analysis.diagnostics
        if direction > 0:
            d = next((d for d in ds if d.line > ln), ds[0])
        else:
            prev = [d for d in ds if d.line < ln]
            d = prev[-1] if prev else ds[-1]
        ed.goto_line(d.line, d.col, d.end)
        self.set_status_message(f'{d.severity.upper()}: {d.message}')

    def rename_symbol(self):
        ed = self.current()
        if not ed:
            return
        old = ed.word_under_cursor()
        old = simpledialog.askstring(APP_NAME, 'Rename this name (targetname, classname, alias...):',
                                     initialvalue=old, parent=self.root)
        if not old:
            return
        new = simpledialog.askstring(APP_NAME, f"New name for '{old}':", initialvalue=old, parent=self.root)
        if not new or new == old:
            return
        pat = re.compile(r'(?<![\w!*@`^.\-])' + re.escape(old) + r'(?![\w])')
        text, n = pat.subn(lambda m: new, ed.get_text())
        if n:
            self.replace_all_text(ed, text)
        self.set_status_message(f"Renamed {n} occurrence(s) of '{old}' to '{new}'")

    def split_lines(self):
        ed = self.current()
        if not ed:
            return
        if ed.text.tag_ranges('sel'):
            first, last = ed.selected_lines()
        else:
            first, last = 1, ed.line_count()
        lines = [ed.text.get(f'{ln}.0', f'{ln}.end') for ln in range(first, last + 1)]
        out = []
        for l in lines:
            out.extend(tslang.split_statements(l))
        if out != lines:
            ed.replace_lines(first, last, out)

    def join_lines(self):
        ed = self.current()
        if not ed or not ed.text.tag_ranges('sel'):
            self.set_status_message('Select the lines to join first')
            return
        first, last = ed.selected_lines()
        lines = [ed.text.get(f'{ln}.0', f'{ln}.end').strip() for ln in range(first, last + 1)]
        parts = []
        for l in lines:
            if not l:
                continue
            if tslang.lex_line(l)[1] is not None:
                messagebox.showwarning(APP_NAME, 'Lines with // comments cannot be joined.', parent=self.root)
                return
            parts.append(l if l.endswith(';') else l + ';')
        ed.replace_lines(first, last, [''.join(parts)])

    def expand_aliases(self):
        ed = self.current()
        if not ed:
            return
        ed._run_analysis()
        aliases = ed.analysis.aliases
        out = [tslang.expand_aliases_line(l, aliases) for l in ed.get_text().split('\n')]
        self.add_editor(None, '\n'.join(out), ed.encoding, ed.newline)

    def strip_comments(self):
        ed = self.current()
        if not ed:
            return
        out = []
        for l in ed.get_text().split('\n'):
            c = tslang.lex_line(l)[1]
            if c is not None and not tslang.is_end_marker(l):
                l = l[:c].rstrip()
                if not l:
                    continue
            out.append(l)
        self.add_editor(None, '\n'.join(out), ed.encoding, ed.newline)

    def toggle_wrap(self):
        self.settings['wrap'] = self.wrap_var.get()
        for ed in self.editors:
            ed.set_wrap(self.settings['wrap'])

    def toggle_ac(self):
        self.settings['autocomplete'] = self.ac_var.get()

    def show_shortcuts(self):
        messagebox.showinfo(APP_NAME, '\n'.join([
            'Ctrl+Space   Autocomplete',
            'Ctrl+E       Insert entity',
            'Ctrl+Shift+O Insert output',
            'Ctrl+T       Insert Test_Wait .1',
            'Ctrl+I       Insert next free hammerid',
            'Ctrl+P       Coordinates (getpos -> origin / setpos)',
            'Ctrl+M       Map entities (browse the map, pick the script\'s map)',
            'Ctrl+`       Game console (live TF2 console + commands)',
            'Ctrl+Shift+P Position from game (getpos into the coordinate dialog)',
            'Ctrl+Alt+Up/Down  Number under cursor +1 / -1 (add Shift for 10)',
            'F9           Run in game (save, then launch TF2 or send to the running game)',
            'Ctrl+F9      Copy the test_startscript command only',
            'Ctrl+/       Toggle comment',
            'Ctrl+D       Duplicate line',
            'Alt+Up/Down  Move line',
            'F2           Rename a name everywhere',
            'F5           Check script',
            'F8 / Shift+F8  Next / previous problem',
            'Ctrl+F / Ctrl+H  Find / replace, F3 find next',
            'Ctrl+G       Go to line',
            'Ctrl+Tab     Next tab',
            'Ctrl+wheel   Zoom',
            'F1           Language reference',
        ]), parent=self.root)

    # -- panels / status --------------------------------------------------
    def on_analysis(self, ed):
        if ed is not self.current():
            return
        a = ed.analysis
        self._fill_problems(a)
        self._fill_outline(a)
        self.update_status(ed)

    def _fill_problems(self, a):
        p = self.problems
        p.delete(*p.get_children())
        self._problem_rows = {}
        icons = {'error': '✖', 'warning': '▲', 'info': '●'}
        for d in a.diagnostics[:2000]:
            iid = p.insert('', 'end', values=(d.line, f'{icons[d.severity]}  {d.message}'), tags=(d.severity,))
            self._problem_rows[iid] = d
        if not a.diagnostics:
            p.insert('', 'end', values=('', '✔  No problems found'), tags=('ok',))
        c = self._counts(a)
        self.problems_info.configure(
            text=f"{c['error']} errors   {c['warning']} warnings   {c['info']} notes" if a.diagnostics else '')

    @staticmethod
    def _counts(a):
        counts = {'error': 0, 'warning': 0, 'info': 0}
        for d in a.diagnostics:
            counts[d.severity] += 1
        return counts

    def _fill_outline(self, a):
        o = self.outline
        top = o.yview()[0]
        for key in ('sections', 'aliases', 'names', 'ids'):
            if o.exists(key):
                self._outline_open[key] = bool(o.item(key, 'open'))
        o.delete(*o.get_children())
        self._outline_lines = {}

        def group(key, title, rows):
            o.insert('', 'end', iid=key, text=f'{title.upper()}   {len(rows)}', open=self._outline_open[key],
                     tags=('group',))
            for text, line in rows:
                iid = o.insert(key, 'end', text=f'{text}', tags=('item',))
                self._outline_lines[iid] = line

        group('sections', 'Sections', [(t, ln) for ln, t in a.sections])
        group('aliases', 'Aliases', [(f'{n}  =  {b}', ln) for n, (ln, b) in a.aliases.items()])
        group('names', 'Names', [(n, defs[0][0]) for n, defs in sorted(a.names.items(), key=lambda kv: kv[0].lower())])
        group('ids', 'Hammer IDs', [
            (f"{k}  {v.get('name') or v.get('cls_new') or v.get('cls')}", v['line'])
            for k, v in sorted(a.hammerids.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)])
        o.yview_moveto(top)

    def _outline_jump(self, _e):
        sel = self.outline.selection()
        ed = self.current()
        if sel and ed and sel[0] in self._outline_lines:
            ed.goto_line(self._outline_lines[sel[0]])

    def _problem_jump(self, _e):
        sel = self.problems.selection()
        ed = self.current()
        if sel and ed and sel[0] in self._problem_rows:
            d = self._problem_rows[sel[0]]
            ed.goto_line(d.line, d.col, d.end)

    def update_status(self, ed):
        if ed is not self.current():
            return
        ln, col = ed.text.index('insert').split('.')
        c = self._counts(ed.analysis)
        sp = self.status_parts
        sp['counts'].configure(text=f"✖ {c['error']}   ▲ {c['warning']}   ● {c['info']}")
        sp['hid'].configure(text=f'hammerid {ed.analysis.next_hammerid()}')
        sp['map'].configure(text=f'map {ed.analysis.map.name}' if ed.analysis.map else 'no map')
        sp['pos'].configure(text=f'Ln {ln}, Col {int(col) + 1}')
        enc = 'UTF-8' if ed.encoding.startswith('utf') else 'ANSI'
        sp['eol'].configure(text=f"{enc}   {'CRLF' if ed.newline == chr(13) + chr(10) else 'LF'}")
        if not getattr(self, '_status_hold', False):
            self.status_help.configure(text=ed.cursor_help())

    def set_status_message(self, msg):
        self._status_hold = True
        self.status_help.configure(text=msg)

        def release():
            self._status_hold = False
        self.root.after(3000, release)

    def run(self):
        self.root.mainloop()


def main():
    app = App(sys.argv[1:])
    app.run()


if __name__ == '__main__':
    main()
