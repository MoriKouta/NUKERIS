from __future__ import print_function

from pathlib import Path

SOURCE = Path("nukeris_dev_1_1_002.py")
TARGET = Path("nukeris.py")

text = SOURCE.read_text(encoding="utf-8")

text = text.replace("NUKERIS v1.1.0-dev.2", "NUKERIS v1.1.0", 1)
text = text.replace('__version__ = "1.1.0-dev.2"', '__version__ = "1.1.0"', 1)

text = text.replace(
    '    "Key_Escape", "Key_Left", "Key_P", "Key_Q", "Key_R", "Key_Return",\n',
    '    "Key_Escape", "Key_Left", "Key_Q", "Key_Return",\n',
    1,
)

text = text.replace(
    '''        QC.Key_A, QC.Key_D, QC.Key_S, QC.Key_W,\n        QC.Key_Q, QC.Key_E, QC.Key_C, QC.Key_R,\n        QC.Key_P, QC.Key_Space, QC.Key_Left,\n''',
    '''        QC.Key_A, QC.Key_D, QC.Key_S, QC.Key_W,\n        QC.Key_Q, QC.Key_E, QC.Key_C,\n        QC.Key_Space, QC.Key_Left,\n''',
    1,
)

text = text.replace(
    '''            if self.error_text:\n                if key == QC.Key_R:\n                    self._new_game()\n                    event.accept()\n                    return\n                event.ignore()\n                return\n''',
    '''            if self.error_text:\n                event.ignore()\n                return\n''',
    1,
)

text = text.replace(
    '''            if self.engine.game_over:\n                if key in (\n                    QC.Key_Space,\n                    QC.Key_Return,\n                    QC.Key_Enter,\n                    QC.Key_R,\n                ):\n''',
    '''            if self.engine.game_over:\n                if key in (\n                    QC.Key_Space,\n                    QC.Key_Return,\n                    QC.Key_Enter,\n                ):\n''',
    1,
)

text = text.replace(
    '''            if key == QC.Key_P:\n                self._set_paused(not self.paused)\n                event.accept()\n                return\n\n''',
    '',
    1,
)

text = text.replace(
    '''                if key == QC.Key_R:\n                    self._new_game()\n                    event.accept()\n                    return\n''',
    '',
    1,
)

text = text.replace(
    '''            elif key == QC.Key_R:\n                if not event.isAutoRepeat():\n                    self._new_game()\n''',
    '',
    1,
)

text = text.replace('sub = "GAME ERROR — R TO RESTART"', 'sub = "GAME ERROR — USE NEW GAME"', 1)

residual = []
for line_number, line in enumerate(text.splitlines(), 1):
    if "QC.Key_P" in line or "QC.Key_R" in line:
        residual.append((line_number, line))
        print("RESIDUAL %d: %s" % (line_number, line))
if residual:
    raise RuntimeError("Release still contains P/R shortcut references")

TARGET.write_text(text, encoding="utf-8")
print("Wrote %s (%d bytes)" % (TARGET, TARGET.stat().st_size))
