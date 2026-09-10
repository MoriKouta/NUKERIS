"""Build the single-file Nuke distribution without importing Nuke or Qt."""
from __future__ import print_function
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = ['core.py', 'geometry.py', 'modes.py', 'ui.py']

def build(include_ui=True):
    parts = []
    for name in PARTS:
        if name == 'ui.py' and not include_ui:
            continue
        with io.open(os.path.join(ROOT, 'src', name), encoding='utf-8') as handle:
            text = handle.read().rstrip()
            if name == 'core.py':
                with io.open(os.path.join(ROOT, 'src', 'storage.py'), encoding='utf-8') as storage:
                    text = text.replace('def _settings_path():', storage.read() + '\n\ndef _settings_path():', 1)
            parts.append(text)
    return '\n\n'.join(parts) + '\n'

if __name__ == '__main__':
    target = os.path.join(ROOT, 'nukeris.py')
    result = build()
    if '--check' in sys.argv:
        with io.open(target, encoding='utf-8') as handle:
            if handle.read() != result:
                sys.exit('nukeris.py is stale; run python tools/build.py')
        print('Distribution is current')
    else:
        with io.open(target, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(result)
