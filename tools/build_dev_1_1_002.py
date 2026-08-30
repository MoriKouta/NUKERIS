from __future__ import print_function

from pathlib import Path

SOURCE = Path("nukeris_dev_1_1_001.py")
TARGET = Path("nukeris_dev_1_1_002.py")

text = SOURCE.read_text(encoding="utf-8")

text = text.replace("NUKERIS v1.1.0-dev.1", "NUKERIS v1.1.0-dev.2", 1)
text = text.replace(
    "- No disk writes / settings files in this development build.",
    "- Writes only nukeris_settings.json next to this script to persist the best score.",
    1,
)
text = text.replace(
    "import math\nimport random\nimport time\nimport traceback\n",
    "import json\nimport math\nimport os\nimport random\nimport time\nimport traceback\n",
    1,
)
text = text.replace('__version__ = "1.1.0-dev.1"', '__version__ = "1.1.0-dev.2"', 1)

marker = "CLEAR_FX_SECONDS = 0.28\n"
settings_code = r'''
SETTINGS_FILENAME = "nukeris_settings.json"


def _settings_path():
    """Return the settings file beside this Python module."""
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), SETTINGS_FILENAME)
    except Exception:
        return None


def _load_best_score():
    """Load a persisted best score. Invalid/missing settings safely fall back to 0."""
    path = _settings_path()
    if not path:
        return 0
    try:
        with open(path, "r") as handle:
            data = json.load(handle)
        value = int(data.get("best_score", 0))
        return max(0, value)
    except Exception:
        return 0


def _save_best_score(best_score):
    """Persist the best score without ever allowing an I/O error to affect Nuke."""
    path = _settings_path()
    if not path:
        return False

    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w") as handle:
            json.dump(
                {"best_score": max(0, int(best_score))},
                handle,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")

        # os.replace() is unavailable in Python 2.7, so use a compatible
        # remove+rename sequence. The temporary file avoids partial JSON writes.
        if os.path.exists(path):
            os.remove(path)
        os.rename(temp_path, path)
        return True
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False
'''
if marker not in text:
    raise RuntimeError("Could not find settings insertion marker")
text = text.replace(marker, marker + settings_code, 1)

old_init = '''    def __init__(self) :\n        self.best_score = 0\n        self.reset()\n\n    def reset(self) :\n'''
new_init = '''    def __init__(self) :\n        self.best_score = _load_best_score()\n        self.reset()\n\n    def _update_best_score(self) :\n        if self.score > self.best_score:\n            self.best_score = self.score\n            _save_best_score(self.best_score)\n\n    def reset(self) :\n'''
if old_init not in text:
    raise RuntimeError("Could not find GameEngine init block")
text = text.replace(old_init, new_init, 1)

best_line = "            self.best_score = max(self.best_score, self.score)"
count = text.count(best_line)
if count != 2:
    raise RuntimeError("Expected 2 indented best-score updates, found %d" % count)
text = text.replace(best_line, "            self._update_best_score()")

best_line_8 = "        self.best_score = max(self.best_score, self.score)"
count = text.count(best_line_8)
if count != 1:
    raise RuntimeError("Expected 1 best-score update, found %d" % count)
text = text.replace(best_line_8, "        self._update_best_score()", 1)

soft_old = '''        if self.move(0, 1):\n            self.score += 1\n            return True\n'''
soft_new = '''        if self.move(0, 1):\n            self.score += 1\n            self._update_best_score()\n            return True\n'''
if soft_old not in text:
    raise RuntimeError("Could not find soft-drop score block")
text = text.replace(soft_old, soft_new, 1)

hard_old = '''        self.score += distance * 2\n        self.lock_piece()\n'''
hard_new = '''        self.score += distance * 2\n        self._update_best_score()\n        self.lock_piece()\n'''
if hard_old not in text:
    raise RuntimeError("Could not find hard-drop score block")
text = text.replace(hard_old, hard_new, 1)

TARGET.write_text(text, encoding="utf-8")
print("Wrote %s (%d bytes)" % (TARGET, TARGET.stat().st_size))
