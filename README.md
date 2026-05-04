# Gen Black Rework

## Status
I decided to improve the project by cleaning the code base and enhancing readability. My aim is to use it for my own needs while adding some quality of life features. As far as I understand, the previous maintainer is not interested in that anymore. The first step of the plan is tidying up the current state, then migrating it to Python 3 completely.

> [!NOTE]
> ### Legal Disclaimer
> These scripts are provided for _**educational and personal use only**_.
> 
> **DO NOT** interfere with any software without owner's permission!  
> **DO NOT** distribute any materials protected by **copyrights**!  
> 
> The author does not encourage or recommend its use by others.  
> Users assume full responsibility for any consequences arising from the use of this tool.

## What does it do?
It decodes some 3D game objects from their original file format to OBJ format or vice versa.

## Requirements
- Python 2.5 or 2.7  
- PIL (Python Imaging Library) for Python 2.5 or 2.7

If you run this script with [PyPy](https://www.pypy.org), it can increase compilation speed by 10-50% depending on project size/quality. (Personally, I can't install PIL on PyPy, so `render_template` does not work.)

It can be used with **[GenBlack Multicore 2020 DLC](https://github.com/PodFolio/GenBlack-Multicore-2020-DLC)**.

<hr>

<details open="open">
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#added-commands">Added commands</a>
      <ul>
        <li><a href="#glue-ressurected">GLUE</a></li>
        <li><a href="#set_texture_slot2">SET_TEXTURE_SLOT2</a></li>
        <li><a href="#submeshes_count">SUBMESHES_COUNT</a></li>
        <li><a href="#mirror_state">MIRROR_STATE</a></li>
        <li><a href="#mesh_type">MESH_TYPE</a></li>
        <li><a href="#mesh_fix">MESH_FIX</a></li>
        <li><a href="#delete_col-ressurected">DELETE_COL</a></li>
        <li><a href="#delete_shadow">DELETE_SHADOW</a></li>
        <li><a href="#delete_model-ressurected">DELETE_MODEL</a></li>
        <li><a href="#delete_blank">DELETE_BLANK</a></li>
        <li><a href="#del">DEL</a></li>
        <li><a href="#check_bb">CHECK_BB</a></li>
        <li><a href="#set_bb">SET_BB</a></li>
        <li><a href="#scale_texture">SCALE_TEXTURE</a></li>
        <li><a href="#move_texture">MOVE_TEXTURE</a></li>
        <li><a href="#front_texture_fix">FRONT_TEXTURE_FIX</a></li>
      </ul>
    </li>
    <li>
      <a href="#modified-commands">Modified commands</a>
      <ul>
        <li><a href="#mirror-glassfix2fix3bodyoffbodyonbodyfix">MIRROR GLASS/FIX2/FIX3/BODYOFF/BODYON/BODYFIX</a></li>
        <li><a href="#render_template">RENDER_TEMPLATE</a></li>
      </ul>
    </li>
    <li><a href="#lfc-live-for-cruise-model-viewer">LFC (Live For Cruise) Model Viewer</a>
      <ul>
        <li><a href="#features">Features</a></li>
        <li><a href="#controls">Controls</a></li>
        <li><a href="#requirements">Requirements</a></li>
        <li><a href="#directory-structure">Directory Structure</a></li>
        <li><a href="#usage">Usage</a></li>
        <li><a href="#building-from-legacy-sources">Building from legacy sources</a></li>
        <li><a href="#known-limitations">Known limitations</a></li>
        <li><a href="#license">License</a></li>
      </ul>
    </li> 
    <li>
      <a href="#misc">Misc</a>
      <ul>
        <li><a href="#lfscarimp-locked-mod-object-dump">LFSCarImp locked mod object dump</a></li>
        <li><a href="#base-vobs">Base vobs</a></li>
        <li><a href="#gen_black-notepad-syntax">Gen_Black Notepad++ syntax</a></li>
      </ul>
    </li>
	<li><a href="#history--credits">History & Credits</a></li>
    <li><a href="#show-your-support">Show your support</a></li>
  </ol>
</details>

---

## Added commands

### GLUE (ressurected)
Welds two objects together to create smooth edges.

```
GLUE <obj_name> <obj_name2> <distance>
```

Example:  
```
GLUE m4_C1_Frnt m4_M1_side 0.005
```

### SET_TEXTURE_SLOT2
Used for fixing 0.6V ALPHA textures.

```
SET_TEXTURE_SLOT2 <0-4 transparent type> <part_name> <texture_name_ALP> <texture_applied_mode> <texture_side> <0-15 slots>
```

**0-4 transparent type:**  
0 - not transparent  
1 - fully transparent  
2 - glass  
3 - light glass  
4 - tinted glass (see tinted glass in original Car2.psh)

Example:  
```
SET_TEXTURE_SLOT2 2 orb2 X_GTW_ALP single top 0 15
```

### SUBMESHES_COUNT
Sets the sub-mesh count for the main mesh (based on an idea by [DemonRed](https://www.facebook.com/demonred8/)). Intended for use with **[GenBlack Multicore 2020 DLC](https://github.com/PodFolio/GenBlack-Multicore-2020-DLC)**.

```
SUBMESHES_COUNT <count>
```

Works like the `MESH 1` command but with an extra step.

Example (if you want a total of 69 meshes, set it to 68: main mesh + 68 sub-meshes = 69):  
```
SUBMESHES_COUNT 68
```

### MIRROR_STATE
Sets the mesh state (based on an idea by [DemonRed](https://www.facebook.com/demonred8/)).

```
MIRROR_STATE <state>
```

**States:**  
`MIRROR_ONLY`  
`MIRROR_FIX_POSSIBLE`

Example:  
```
MESH 1
MIRROR_STATE MIRROR_ONLY
```

### MESH_TYPE
Sets the mesh type (based on an idea by [DemonRed](https://www.facebook.com/demonred8/)).

```
MESH_TYPE <type>
```

**Types:**  
`MAIN` - main mesh  
`CALIPER` - brake caliper  
`WHEEL` - steering wheel  
`DEFAULT` - default mesh  
`ALWAYS_VISIBLE` - always visible, even in F mode  
`MIRROR` - central rearview mirror

Example:  
```
MESH 5
MESH_TYPE ALWAYS_VISIBLE
```

### MESH_FIX
Sets the mesh fix flag (based on an idea by [DemonRed](https://www.facebook.com/demonred8/)).

```
MESH_FIX <state>
```

**States:**  
`ON` - mirror fix works  
`OFF` - mirror fix does not work

Example:  
```
MESH 2
MESH_FIX OFF
```

### DELETE_COL (ressurected)
Deletes collision.

```
DELETE_COL <part_name>
```

### DELETE_SHADOW
Deletes shadow.

```
DELETE_SHADOW <part_name>
```

### DELETE_MODEL (ressurected)
Deletes parts by specific model.

```
DELETE_MODEL <part_name>
```

Example:  
```
MODEL 4
DELETE_MODEL M1_side
```

### DELETE_BLANK
Remove all faces from unnamed (blank) objects.

```
DELETE_BLANK
```

Example:  
```
MESH 1
DELETE sheild
DELETE_BLANK
DELETE l_brk
```

### DEL
Combined `DELETE_SHADOW` / `DELETE_COL` / `DELETE_MODEL` command.

```
DEL <part_name> <0-2 collision/shadow> <model>
```

**collision/shadow:**  
0 - no collision/shadow  
1 - shadow  
2 - collision

**model:**  
0-9 - model number  
-1 - no model chosen

Example:  
```
DEL M1_side 2 4
```

### CHECK_BB
Checks texture boundaries.

```
CHECK_BB <part_name>
```

Example:  
```
CHECK_BB M1_side
```

### SET_BB
Sets new texture boundaries.

```
SET_BB <part_name> <x1> <x2> <y1> <y2>
```

Example:  
```
SET_BB M1_side -2.5 2.0 0.5 1.2
```

### SCALE_TEXTURE
Scales texture (float, 1 = 100%).

```
SCALE_TEXTURE <part_name> <scale>
```

Example:  
```
SCALE_TEXTURE M1_side 0.5
```

### MOVE_TEXTURE
Moves texture.

```
MOVE_TEXTURE <part_name> <left/right> <up/down>
```

Example:  
```
MOVE_TEXTURE M1_side 1.5 1.2
```

### FRONT_TEXTURE_FIX
Simple front texture fix.

```
FRONT_TEXTURE_FIX <part_name>
```

Example:  
```
FRONT_TEXTURE_FIX plate_Front
```

## Modified commands

### MIRROR GLASS / FIX2 / FIX3 / BODYOFF / BODYON / BODYFIX
Added more mirror variants.

- `FIX2` / `FIX3` work like normal `FIX`.
- `GLASS` adds "smooth" for glass (like in original vob; unclear if it actually does anything).
- `BODYOFF` / `BODYON` / `BODYFIX` add "smooth" for body parts (like in original vob; unclear if they actually do anything — use only on `MESH 1`).

### RENDER_TEMPLATE
Now you can choose whether to use the old JPG method or the new transparent PNG method by adding `.jpg` or `.png` at the end of the filename.

Example:  
```
RENDER_TEMPLATE l_find 33_LIGHTS1.png 0
```

## LFC (Live For Cruise) Model Viewer

A unified OpenGL viewer for `.vob` and `.wld`/`.cem` mesh files. Combines low‑level VOB parsing with the Blackwood API for WLD files, providing an interactive 3D inspection tool.

![Screenshot Placeholder]()

### Features

- **Dual format support** – open `.vob` (mesh parts) and `.wld` / `.cem` (complete vehicles) files.
- **Interactive camera** – orbit, pan, dolly, zoom, auto‑rotate.
- **View modes** – wireframe, X‑ray, isolate selected object, glowing outline.
- **Mesh navigation** – switch between sub‑meshes (Page Up/Down).
- **Object selection** (VOB mode) – cycle through named parts (`1` / `2` keys).
- **Background colour palette** – 33 presets, cycle with `3` / `4`.
- **Auto‑fit** – automatically adjust camera distance and target (`F` key).
- **On‑screen HUD** – shows current background and mode toggles.
- **Ground grid** – reference grid on the XY plane (Z=0).

### Controls

| Category | Keys / Mouse |
|----------|---------------|
| **Orbit** | Left drag / Arrow keys |
| **Dolly** | Middle drag / `W` `S` |
| **Pan** | Right drag / `A` `D` (horizontal), `Q` `E` (vertical) |
| **Zoom** | Mouse wheel / `+` `-` |
| **Auto‑rotate** | `R` |
| **Fit view** | `F` |
| **Wireframe** | `Z` |
| **X‑ray** | `X` |
| **Isolate** | `C` |
| **Outline** | `V` |
| **Mesh prev/next** | Page Down / Page Up |
| **Select object (VOB)** | `1` (previous), `2` (next) |
| **Background colour** | `3` (previous), `4` (next) |
| **Exit** | `ESC` |

### Requirements

- Python **2.7**
- OpenGL, GLUT, GLU bindings (`PyOpenGL 3.1.6`, `freeglut`)
- `PIL` / `Pillow`
- `blackwood` – custom file access module

### Directory Structure

Textures are looked up in `tex/jpg/` relative to the working directory.  
Place your `.jpg` texture files there (e.g. `tex/jpg/HEL_DEFAULT.jpg`).

### Usage

```bash
python viewer.py <file.vob> [mesh_id]
python viewer.py <file.wld> [mesh_id]
python viewer.py <file.cem> [mesh_id]
```

- `mesh_id` is optional (default = 1). For VOB files it selects the sub‑mesh (if the file contains multiple meshes). For WLD/CEM it selects the mesh index inside the file.

Examples:

```bash
python viewer.py veh/XR.vob
python viewer.py veh/Blackwood.wld 40
```

### Building from legacy sources

This viewer merges and improves two deprecated original scripts:

- `view_things.py` – WLD viewer using the Blackwood API.
- `vob_view.py` – low‑level VOB parser.

Key improvements over the originals:

- Interactive camera instead of fixed rotation.
- Stencil‑based outline selection.
- Multiple view toggles (wireframe, X‑ray, isolate).
- Background colour palette.
- Sub‑mesh switching.
- Auto‑fit and bounding box calculation.
- Proper Z‑up coordinate handling for VOB geometry.
- Texture cache and display list reuse.

### Known limitations

- Textures are expected in `tex/jpg/`; paths are not configurable at runtime.
- Only `.jpg` textures are supported.
- Python 2.7 only (due to `blackwood` module and legacy code).

## Misc

### LFSCarImp locked mod object dump
Use `is_file_locked = True` flag in `vob_obj.py` to dump locked LFSCarImp vob files.

### Base vobs
In the `BASE` folder:

- `P` folder contains default vob bases from before the virtual mirrors ("big wing") update.
- `R` folder contains default vob bases from after the virtual mirrors ("big wing") update, compatible with 0.6V.
- `Custom` folder contains custom vob bases.

### Gen_Black Notepad++ syntax
Syntax highlighting for Notepad++.

Go to *Language > User Defined Language > Define your language... > Import* and select `genblack.xml`.

It works with [Visual Studio 2019 Dark Theme for Notepad++](https://github.com/hellon8/VS2019-Dark-Npp).

Example:  
![Gen_Black Notepad++ syntax](https://i.imgur.com/eDhyuZN.png)

## History & Credits
_(**2009** - initial release by original author)_
Rangel Fisica's [version](https://linhasverticais.wordpress.com/gen_black/)

_(**2013** - complete package with a few improvements)_
Frito's [version](https://static1.downloadgamemods.com/Live%20for%20Speed/Tools/lfsdk.7z) (dead - will be updated later)

_(**2020** - modded with additional commands)_
PodFolio's [version](https://github.com/PodFolio/gen_black-mod)

_(**2026** - bug fixes, cleaned code base and additional features)_
Rework [version](https://github.com/obdegirmenci/gen-black-rework)

## Show your support
Please ⭐️ this repository if this project helped you. Volunteers are welcome.
