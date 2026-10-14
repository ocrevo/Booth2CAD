"""List text files in the working copy that contain CRLF (the repository stores LF; release evidence hashes working-copy bytes).

    python tools/check_lf.py          # prints offenders, exit code 1 if any

Checks tracked, modified and untracked-but-not-ignored files; skips binaries, the raw regression evidence and vendored code.
`grep -l $'\r'` is not reliable in every shell on this machine, so use this instead.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PREFIX = ('booth-image-to-model/validation/', 'web/app/vendor/')
SKIP_SUFFIX = ('.png', '.jpg', '.jpeg', '.glb', '.blend', '.pdf', '.zip')


def listed(*args):
    out = subprocess.run(['git', '-C', str(ROOT), 'ls-files', *args], capture_output=True, text=True, check=True).stdout
    return [line for line in out.split('\n') if line]


def main() -> int:
    names = sorted(set(listed()) | set(listed('-m', '-o', '--exclude-standard')))
    bad = [n for n in names if not n.startswith(SKIP_PREFIX) and not n.endswith(SKIP_SUFFIX)
           and (ROOT / n).is_file() and b'\r\n' in (ROOT / n).read_bytes()]
    for n in bad:
        print(n)
    print(f'{len(bad)} file(s) with CRLF' if bad else 'all text files use LF', file=sys.stderr)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
