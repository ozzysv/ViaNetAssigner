# Via Net Assigner

**Via Net Assigner** is a KiCad 10 IPC plugin that lets you copy a net from a PCB pad or track to one or more vias by simply selecting objects in the PCB Editor.

![KiCad](https://img.shields.io/badge/KiCad-10.x-blue)
![Version](https://img.shields.io/badge/version-1.0.6-green)
![API](https://img.shields.io/badge/API-IPC-purple)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Features

- Select a **pad**, **track**, or **arc track** to remember its net.
- Select **vias** one by one to assign the remembered net.
- Selecting another pad or track immediately changes the source net.
- Selecting a pad or track without a net clears the previous source net.
- **Only vias are modified**; source pads and tracks are never changed.
- Protects vias that already have a different net by default.
- Optional **Overwrite via with net** checkbox allows deliberate reassignment.
- Skips locked vias.
- Displays the current net, assignment count, and operation status.
- Compact, non-modal, **always-on-top** window with a **Close** button.
- Remembers one shared window position between launches.
- Supports multiple PCB Editor instances using separate IPC sessions.
- Prevents duplicate plugin instances within the same PCB Editor.
- Built using the modern KiCad IPC API (`kicad-python` / `kipy`), not the legacy SWIG interface.

## Requirements

- **KiCad 10.x**, with IPC API support enabled.
- **Windows** (the current PCM package targets Windows).
- Python runtime supplied with KiCad 10.
- `kicad-python >= 0.8.0 (listed in `requirements.txt`).
- `wxPython` for the graphical interface.

## Installation

### Install from an archive using the KiCad Plugin and Content Manager (PCM)

**Install the PCM ZIP archive directly; do not extract it or copy the plugin folder manually.**

1. Download the **Via Net Assigner PCM ZIP** package (for example, from the project's release assets).
2. Open **KiCad Project Manager**.
3. Open **Plugin and Content Manager**.
4. Select **Install from File...**.
5. Choose the downloaded `.zip` archive.
6. Confirm the installation.
7. Open or restart **PCB Editor** and find **Via Net Assigner** in its plugin toolbar or menu.

> **Important:** Use the specially prepared **PCM ZIP**, not GitHub's automatically generated **Source code (ZIP)** archive. The PCM package contains the required `metadata.json` and plugin files.

If you previously installed Via Net Assigner by copying its files to the KiCad user plugins folder, remove that old manual copy before installing the PCM version to avoid duplicate plugin entries.

## Usage

1. Open your board in **KiCad PCB Editor**.
2. Launch **Via Net Assigner** from the plugin toolbar or menu.
3. Click a **pad** or **track** to select the source net. Its name appears in the small plugin window.
4. Click a **via** to assign it to that net.
5. Continue selecting other vias, or select a different pad/track to switch to another net.
6. To change an existing via net, explicitly check **Overwrite via with net**.
7. Click **Close** to exit the plugin.

The plugin processes a **single selected object** at a time and automatically clears the selection after processing it. It cannot assign a net until a valid source pad or track has been selected.

**Safety:** Reassigning a via that already belongs to another net can create electrical connectivity or DRC issues. The overwrite option is disabled by default; review your board and run DRC after deliberate changes.

## Settings

Via Net Assigner remembers the last window position in a simple `settings.json` file stored **inside the installed plugin directory**.

```json
{
  "x": 150,
  "y": 200
}
```

Only **one shared position** is stored, regardless of how many boards or PCB Editor instances you use. If a saved position is no longer visible on any connected monitor, the window opens centered.

Because settings are stored in the plugin directory, they may need to be backed up before removing or reinstalling the plugin.

## KiCad IPC API

Via Net Assigner uses the modern KiCad **IPC API** via `kicad-python` (`kipy`). It connects to the **specific PCB Editor instance that launched it**, rather than selecting an arbitrary open board.

Its small `wxPython` window stays open while the PCB Editor remains usable. The plugin watches for PCB object selections and modifies **only the selected vias**.

## Version

Current version: **1.0.6**

### Version 1.0.6

- Simplified and cleaned up the plugin implementation.
- Kept a single window-position setting rather than per-board settings.
- Clears the remembered source net when a no-net pad or track is selected.
- Supports the **Overwrite via with net** label and multiple icon sizes (24, 32, 48, and 64 px).

## License

GPL-3.0 license
