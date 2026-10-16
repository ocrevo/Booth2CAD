# Contributing

Thanks for helping. This file says how to set up, which checks to run, and the few rules that keep the project safe to publish.
Coding agents: read [AGENTS.md](AGENTS.md) as well.

## Set up

| You need | For |
|---|---|
| Python 3.10+ (3.12 tested) | everything |
| `pip install -r booth-image-to-model/requirements.txt` | the engine and the studio |
| Blender 4.x or newer (5.2.2 tested), optional | building `.blend` files, renders, the native tests |
| Node.js 22.15+, optional | the web tests |
| Chrome, Chromium or Edge, optional | the browser smoke tests |

```bash
git clone https://github.com/ocrevo/Booth2CAD.git booth-image-to-model
cd booth-image-to-model
python3 -m venv .venv && . .venv/bin/activate          # Windows: py -3 -m venv .venv ; .venv\Scripts\activate
python -m pip install -r booth-image-to-model/requirements.txt
export BLENDER_EXE=/path/to/blender                  # optional; Windows: $env:BLENDER_EXE="C:\...\blender.exe"
```

## Checks

Run what touches your change. A pull request should leave all of them green.

```bash
python tools/check_lf.py                                         # every text file uses LF line endings
python booth-image-to-model/tests/run_tests.py --output output/_validation/my-check   # skill tests (Blender tests skip without Blender)
cd web
npm test                 # editor geometry/camera parity, edit operations, studio decisions and wording (needs Python too)
npm run test:server      # the studio server through its real HTTP API; an OpenAI stand-in, never a real key
npm run smoke            # headless browser drives the standalone editor
npm run smoke:studio     # headless browser drives the studio end to end (Blender steps run when Blender is found)
```

`run_tests.py --require-native` (with Blender) is what a release needs; maintainers run it, see [docs/maintainers.md](docs/maintainers.md).

## Rules

- **No client material.** Never commit client pictures, brand names, project names, client file names or dimensions read from a
  client picture. Use synthetic material (see `web/tools/make_demo.py`, `web/tests/make_studio_fixtures.py`). Keep real pictures in
  the git-ignored `input/` and results in `output/`.
- **No invented facts.** Dimensions, brands, text and certifications are never made up; every assumed value is recorded as
  assumed. The tool gives estimates, not measurements: do not describe it as CAD or as construction-grade.
- **LF line endings** in every tracked text file (`python tools/check_lf.py`).
- **The skill is self-contained.** `booth-image-to-model/` must not depend on `web/`; the web server reaches the engine only
  through `web/server/engine.py`.
- **No new dependencies** (Python packages, npm packages, models, asset packs) without discussing it in an issue first. three.js is
  vendored at a pinned version.
- **Release evidence is generated.** Do not edit `booth-image-to-model/release_status.json`, `FILE_MANIFEST.json` or
  `validation/` by hand; a maintainer regenerates them when releasing. A change to `scripts/`, `schemas/` or `tests/` of the skill
  also needs a `CHANGELOG.md` entry.
- **Plain words in the studio.** The main path of the studio uses no engineering terms; a test scans `web/app/js/studio_copy.js`.
- One topic per pull request, with a message that says what changed and why.

## Reporting

Bugs and ideas: GitHub issues (the templates ask the right questions). Security problems: privately, see [SECURITY.md](SECURITY.md).
By contributing you agree that your contribution is licensed under the [Apache License 2.0](LICENSE).
