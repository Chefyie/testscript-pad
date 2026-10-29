# Testscript-Pad

An editor for **Orange Box / TF2 testscripts** that understands the testscript language, so you don't have to write them in Notepad.

Testscripts are text files of console commands (`ent_fire`, `give`, `ent_keyvalue`, `Test_Wait`, ...) that the game runs from top to bottom. People use them to build whole gamemodes: KOTH on 2Fort, Payload on Dustbowl, CTF on Hydro, Zombie Fortress and so on. Testscript-Pad adds syntax highlighting, autocomplete, a script checker and builders for the long entity blocks these scripts are made of.

## Requirements

- Windows (it also runs on other systems, but the dark title bar and some defaults are Windows-only)
- [Python 3](https://www.python.org/downloads/) with tkinter (the standard Windows installer includes it)
- No extra packages

## Getting started

1. Download or clone this repository.
2. Double-click **`Testscript-Pad.bat`**, or drag `.txt` testscripts onto it.

You can also run it directly:

```bash
pythonw testscript_pad.py path/to/script.txt
```

The open dialog starts in `D:\Games\game\tf\testscripts` if that folder exists. Open tabs are restored the next time you start the editor.

## Features

### Syntax highlighting

| Color | Meaning |
|---|---|
| blue, bold | commands: `ent_fire`, `give`, `ent_keyvalue`, `alias`, ... |
| purple, bold | `Test_` commands: `Test_Wait`, ... |
| yellow, bold | your aliases (`a;`, `b;`, ...) |
| teal | entity classes: `logic_relay`, `math_counter`, ... |
| light blue | names and targets (bold where the name is defined) |
| gold | inputs: `addoutput`, `trigger`, `setteam`, ... |
| violet, bold | outputs: `OnTrigger`, `OnPass`, `OnCase01`, ... |
| orange | keyvalues: `origin`, `classname`, `hammerid`, ... |
| green, italic | `//` comments |
| red | the `///` end marker (everything after it is greyed out) |

Inside outputs, `"target,input,parameter,delay"` is colored field by field.

### Autocomplete

Suggestions appear as you type (or press `Ctrl+Space`) and depend on where the cursor is:

- **First word:** commands and your aliases
- **After `ent_fire`:** names and classes, then inputs
- **Inside `addoutput"...`:** keyvalues and outputs
- **After an output:** targets, then inputs after the first comma
- **After `ent_keyvalue`:** your hammerids
- **After `prop_dynamic_create`:** models

The status bar explains the word under the cursor: what a command, input or output does, what an alias expands to, or which entity a hammerid belongs to.

### Script checker

The **Problems** panel updates as you type. `F5` runs the check and `F8` jumps to the next problem. It flags:

- a missing `///` end marker, or text after it
- `ent_keyvalue` on a hammerid that was never assigned
- `ent_keyvalue` right after `addoutput"hammerid N` with no `Test_Wait` in between (`ent_fire` is queued, so the entity doesn't have the id yet)
- the same hammerid assigned twice, or the same targetname given to two new entities
- `Test_Wait` without a number (e.g. `test_wait .1:`)
- `ent_fire` whose target looks like an input (a missing space or a doubled word)
- unknown commands (typos, undefined aliases) and unknown entity classes
- outputs with too many fields, and unused or redefined aliases

### Builders

- **Entity... (`Ctrl+E`)** writes the whole spawn block for you, in either style:
  - compact: `give x;ent_fire x addoutput"hammerid N";test_wait .1;ent_keyvalue N ...`
  - step by step: `give x;` then `ent_fire x addoutput"classname name;` ... `Test_Wait .1;`
- **Output... (`Ctrl+Shift+O`)**, **Alias...**, **Test_Wait** (`Ctrl+T`), **next free hammerid** (`Ctrl+I`)
- Snippets for point_clientcommand/point_servercommand, respawn times and goal text, restart round, and `///`

### Run in game

Press **`F9`** (or **▶ Run** on the toolbar). The editor saves the script and then:

- **If TF2 isn't running,** it starts `hl2.exe` with your launch options, loads the map that matches the script's folder, waits a few seconds, and runs the script. For example, `Gamemodes/2Fort/KOTH.txt` loads `ctf_2fort`, `Dustbowl` loads `cp_dustbowl` and `Hydro` loads `tc_hydro`. It does this through a small launcher testscript, `tf\testscripts\testscript_pad_launch.txt`, which is rewritten on every run and is safe to delete.
- **If TF2 is already running,** it sends `test_startscript <script>` to that game with `-hijack` instead of opening a second copy.

Either way, the `test_startscript Gamemodes/2Fort/KOTH.txt` command is also copied to the clipboard. `Ctrl+F9` only copies it, without launching.

The script must be saved somewhere under `tf\testscripts\`. The game folder (the one with `hl2.exe`) is found from where the script is saved. You can set it yourself under **Tools → Game settings...**, along with:

- **Launch options:** `-testscript` is added for you. The default is `-game tf 440 -sw -w 1920 -h 1080 -port 27016 -novid -dev -console -insecure -toconsole -nohltv -nomaster`.
- **Map to load:** auto (from the folder name), a fixed map, or none (run the script straight at startup)
- **Map when the folder has no match:** used for scripts in folders like `Any`. The default is `ctf_2fort`.
- **Seconds to wait before the script starts:** default 20. The countdown starts when the map starts loading, and connecting to your own server takes around 13 seconds on 2Fort. Starting a script before you're in the game crashes TF2, so raise this if the game crashes on launch.
- **Run in the already-running game:** on by default
- **Clipboard command:** `{path}` is the path from the testscripts folder, `{name}` is just the file name

### Coordinates

**Coordinates... (`Ctrl+P`)** turns positions into script text:

1. Type `getpos` in the TF2 console and copy the `setpos ...;setang ...` line it prints.
2. Open the dialog. It picks up the copied line from the clipboard automatically. You can also paste it, type the numbers, or click **From line** to read the `origin`/`angles` already on the cursor line.
3. Add an offset if you want (for example `-64` on Z), choose how to round, and pick a format:
   - `origin"x y z"`, for `ent_keyvalue` and `ent_create`
   - `ent_fire <name> addoutput"origin x y z;`
   - `name,addoutput,origin x y z`, for use inside an output
   - `setpos x y z;setang p y r;`
   - plain `x y z`
4. Click **Insert** or **Copy**.

To fine-tune a number in place, put the cursor on it and press `Ctrl+Alt+Up` / `Ctrl+Alt+Down` (±1), or add `Shift` for ±10.

### Tools

- Rename a name everywhere (`F2`)
- Split `;`-joined commands onto separate lines, or join selected lines into one
- Expand aliases into a new tab
- Remove comments into a new tab
- Searchable language reference (`F1`)

### Layout

- **Toolbar** for the common actions (hover over a button to see its shortcut)
- **Tabs:** an × on each tab closes it, or middle-click the tab
- **Panels:** an × on the **Outline** / **Problems** headers hides them, and the View menu brings them back. Drag the dividers to resize; sizes are remembered.
- **Outline:** sections (`//` comment lines), aliases, names and hammer IDs. Click one to jump to it.
- **Status bar:** problem counts (click one to jump to the next problem), next free hammerid, line/column, encoding and line endings
- Dark and light themes, zoom with `Ctrl+mouse wheel`

### Editing

- Find/replace with regex (`Ctrl+F` / `Ctrl+H`), go to line (`Ctrl+G`)
- Toggle comment (`Ctrl+/`), duplicate line (`Ctrl+D`), move lines (`Alt+Up/Down`)
- Files keep their original encoding and line endings when saved

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Space` | Autocomplete |
| `Ctrl+E` | Insert entity |
| `Ctrl+Shift+O` | Insert output |
| `Ctrl+T` | Insert `Test_Wait .1` |
| `Ctrl+I` | Insert next free hammerid |
| `Ctrl+P` | Coordinates (getpos → origin / setpos) |
| `Ctrl+Alt+Up` / `Ctrl+Alt+Down` | Number under the cursor +1 / −1 (add `Shift` for ±10) |
| `F9` | Run in game (save, then launch TF2 or send to the running game) |
| `Ctrl+F9` | Copy the `test_startscript` command only |
| `Ctrl+/` | Toggle comment |
| `Ctrl+D` | Duplicate line |
| `Alt+Up` / `Alt+Down` | Move line |
| `F2` | Rename a name everywhere |
| `F5` | Check script |
| `F8` / `Shift+F8` | Next / previous problem |
| `Ctrl+F` / `Ctrl+H` / `F3` | Find / replace / find next |
| `Ctrl+G` | Go to line |
| `Ctrl+Tab` | Next tab |
| `F1` | Language reference |

## Project layout

| File | Purpose |
|---|---|
| `testscript_pad.py` | the editor window |
| `tslang.py` | the testscript language: vocabulary, highlighting, autocomplete context, checker |
| `Testscript-Pad.bat` | Windows launcher |

Settings are stored in `%APPDATA%\Testscript-Pad\settings.json`.

To teach the editor new commands, inputs, outputs, keyvalues or entity classes, add a line to the matching table at the top of `tslang.py` (`name | description`).

## License

[MIT](LICENSE) © 2026 Chefy
