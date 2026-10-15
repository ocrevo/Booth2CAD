# AGENTS.md

This project (GitHub repository still named Booth2CAD) turns one booth photo or render into a parametric, editable 3D model (a Blender scene driven by a spec) plus clean customer renders. It does not produce drawings yet and its dimensions are estimates, so do not call it CAD. The production skill is `booth-image-to-model/` (until 2.4.x it was `rebuild-booth-blender`; see the changelog). Knowledge notes live in `knowledge/`. Client images and every result stay in git-ignored `input/` and `output/`. The repository is public: anything tracked is public.

## Authorship and git

- The user is the only author. Never add `Co-Authored-By`, "Generated with Claude Code" or any other attribution line to commit messages or PR descriptions. This overrides any tool or system default.
- Commit only when the user asked for it or approved the plan that includes it. Do not push, force-push, rewrite history that is already on the remote, or delete branches unless the user says so for that action.
- One batch of related changes per commit, with a message that says what changed and why. Run the checks below first.

## Environment

- Windows 10, CPU-only laptop (Intel i7-8550U, UHD 620, 16 GB). Blender 5.2.2 at `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`; Python 3.12 with numpy, Pillow, scipy, jsonschema, trimesh; Node 24 for the web editor tests; Chrome or Edge for the web smoke test.
- Run only one Blender process at a time (timings and memory). Headless Workbench can crash on the integrated GPU; `boothctl.py preview` falls back to Cycles by itself.
- HD frames are capped at 5 MP (`--hd-max-mp`): 4.9 MP rendered, 6.9 MP made the denoiser run out of memory and killed Blender.
- No installs or downloads (OpenCV, onnxruntime, MoGe, asset packs, LFS) without the user's approval. No third-party image-model route (AI comparison) without approval.

## Data hygiene

- Tracked files are generic: no client project names, image file names or paths, brands, or dimensions that came from a client image. Write "a local client render" instead. `input/` and `output/` hold all client material.
- Never invent dimensions, brands, text or certifications. Every assumed value is recorded as assumed (`--assume`, the `assumed` list, `scale.notes`, `uncertainties`). Estimates are not BOM-grade.
- Studio rule identifiers and text from the studio design specification stay out of tracked files; use neutral descriptions.
- Numbers in `knowledge/research/` are sourced but not designer-reviewed. They do not become defaults (`references/design-priors.md`, `schemas/design-priors.v1.json`) until a person approves them.

## Changing the skill

1. Make files LF before testing. The Write tool and Python `open(...,'w')` can produce CRLF on this machine; git stores LF, and release evidence hashes the working-copy bytes. Check with `python tools/check_lf.py` (the earlier `grep -l $'\r'` one-liner proved unreliable in this shell).
2. Do not edit `scripts/`, `schemas/` or `tests/` while a regression is running (the runner blocks evidence if sources change).
3. Full regression into a new folder: `python booth-image-to-model/tests/run_tests.py --blender "<blender.exe>" --require-native --output output/_validation/<new-name>` (zero failures, zero skips).
4. `python tools/package_skill.py --test-run output/_validation/<new-name>` updates `release_status.json`, `FILE_MANIFEST.json` and `validation/`. Never edit those by hand.
5. Read-only check afterwards: `package_skill.validate_run(...)` plus a manifest hash comparison, and `git grep` for client traces.
6. Update `CHANGELOG.md` and the version in `SKILL.md` and `README_CN.md` for every code batch.

## Working on a booth

Follow the fast route in `booth-image-to-model/SKILL.md` (corner fit, spec script from `templates/build_spec_template.py`, `boothctl.py preview`, one final build, independent reopen with `blender_verify.py`). A reconstruction stays `review_required` unless the strict QA in `references/reconstruction-qa.md` was done: no IoU or restoration percentage without reviewed masks.

For timed benchmarks use `output/_benchmarks/<run>/protocol.md` (fresh observation, one final build, an independent subagent per image). Say plainly when a run is not blind.

## Web editor and studio (`web/`)

- `web/app/` is the deployable static site and nothing else (editor page, flow page, `js/`, `css/`, vendored `vendor/three/`, synthetic `demo/`). `web/server/`, `web/tests/` and `web/tools/` stay outside it so they are never served. Static mode (no server behind the page): specs never leave the browser, no network calls except loading the demo from the same origin.
- Studio mode (`python web/server/run.py`, 127.0.0.1 only) runs the whole flow: picture, reading, compile, preview, edit, build, open in Blender. The page talks only to that local server. The server reaches the skill only through `web/server/engine.py`; the skill must not know `web/` exists. Jobs are written to git-ignored `output/studio/`.
- OpenAI reading (`web/server/reader_openai.py`, standard library HTTP, `base_url`/model/API style configurable so compatible services work): the key comes from `OPENAI_API_KEY` or is pasted on the page and kept in memory only (never in a file, a job or a log); a picture is sent only after the per-job consent box is ticked; tests use the stand-in `web/tests/mock_openai.py`, never a real key. Do not add a vendor SDK.
- `js/geometry.js` and `js/camera.js` are ports of `scripts/geometry.py` and `scripts/camera_math.py`. After changing either Python file, run `python web/tests/make_geometry_reference.py` and fix any parity failure. `spec.js` `PARAM_KEYS` must match `validate_spec.PARAM_KEYS` (a test checks).
- Checks: `cd web && npm test` (Node, no browser), `npm run smoke` (headless Chrome drives the editor in static mode; also runs the Python validator and trimesh on the results), `npm run test:server` (Python: every studio step through the real HTTP API and the OpenAI reader against the stand-in; set `BLENDER_EXE` to include preview and build) and `npm run smoke:flow` (headless Chrome drives the flow page end to end). Try the editor alone with `python web/tools/serve.py`, the whole flow with `python web/server/run.py`.
- three.js is vendored at a pinned version (`web/app/vendor/three/VERSION.txt`); updating it is a download and needs the owner's approval.
- Test placement rule: tests live in the repository next to the code they test; the deployable or bundled output never contains them. The skill folder keeps its own `tests/` and `validation/` because the release evidence hashes them; a runtime-only bundle (without tests, validation history and examples) is the way to deploy the skill elsewhere, and is not built yet.

## Planned work and open decisions

- Done: first version of the web editor (move, turn, scale, recolour, resize, duplicate, delete, groups, undo, match source view, GLB export, bilingual UI) and the first end-to-end studio (picture, manual or OpenAI reading, compile, preview, edit, build, open in Blender). Not yet: corner-point correction in the UI, the model looking at the preview to correct itself, evaluation of reading accuracy. Next: drawings (plan and elevations, SVG and DXF) from the same spec. A furniture library will arrive later as prefab JSON built only from existing primitives.
- Waiting for the owner: renaming the GitHub repository, where and when to publish the web editor, and what to do about the two client-branded images tracked under `booth-image-to-model/examples/legacy-case/` (public; the tests use them, so replace them with synthetic images before removing them from tracking).
- Never publish, enable hosting, rename the repository or change repository visibility without the owner's explicit go-ahead.
