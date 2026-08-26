# NUKERIS

A Nuke-native falling-block puzzle game designed for quick breaks while compositing.

<img width="1173" height="1729" alt="image" src="https://github.com/user-attachments/assets/504ff70a-c21d-4f23-87ed-9b6c0e22f778" />


NUKERIS runs directly inside Foundry Nuke as a dockable PySide6 panel. Its visual language is inspired by Nuke's Node Graph and Properties panels: pieces are drawn as connected Nuke-style nodes, with familiar node colors, wires, and an optional Node Graph grid.

## Features

- Dockable Nuke panel
- Nuke-inspired Node Graph interface
- Connected node-style pieces
- Optional Node Graph grid
- Hold piece
- Next piece queue
- Ghost piece
- Soft Drop / Hard Drop
- Wall kicks
- Combo scoring
- Line-clear effects
- Session timer
- Automatic pause when input focus is lost
- Keyboard handling designed to avoid conflicts with Nuke shortcuts

## Controls

| Key | Action |
| --- | --- |
| A / D | Move |
| S | Soft Drop |
| Q / E | Rotate |
| C | Hold |
| Space / W | Hard Drop |
| P | Pause |
| R | New Game |
| Esc | Pause / Release Input |

Keyboard controls are active only while the NUKERIS panel owns input focus.

## Installation

1. Copy `nukeris.py` into your `.nuke` directory.

   **Windows**
   ```text
   C:\Users\<USERNAME>\.nuke\nukeris.py
   ```

   **Linux**
   ```text
   ~/.nuke/nukeris.py
   ```

2. Add this line to your existing `menu.py`:

   ```python
   import nukeris
   ```

3. Restart Nuke.
4. Open **Pane → NUKERIS**.

The panel can then be docked anywhere in your Nuke workspace.

### Optional: keep it in a subfolder

For a personal setup, you can keep the file in `.nuke/game/nukeris.py`. Add the folder to Nuke's plugin path from `init.py`:

```python
import nuke
nuke.pluginAddPath("./game")
```

Then keep the same line in `menu.py`:

```python
import nukeris
```

## Safety

NUKERIS is intentionally isolated from your comp. It does not:

- create, delete, select, or modify nodes
- modify knobs
- modify the Viewer
- change the current frame or timeline
- modify the Undo stack
- write data into the current `.nk` script
- register global keyboard shortcuts

The game receives keyboard input only while its panel has focus.

## Compatibility

- Foundry Nuke / NukeX 16.0+
- PySide6
- Windows
- Linux

## License

MIT License. See [LICENSE](LICENSE).

## Author

Kota Mori

NUKERIS v1.0.0  
© 2026 Kota Mori
