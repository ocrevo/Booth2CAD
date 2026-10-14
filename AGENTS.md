# AGENTS.md

This project (GitHub repository still named Booth2CAD) turns one booth photo or render into a parametric, editable 3D model (a Blender scene driven by a spec) plus clean customer renders. It does not produce drawings yet and its dimensions are estimates, so do not call it CAD. The production skill is `booth-image-to-model/` (until 2.4.x it was `rebuild-booth-blender`; see the changelog). Knowledge notes live in `knowledge/`. Client images and every result stay in git-ignored `input/` and `output/`. The repository is public: anything tracked is public.

## Authorship and git

- The user is the only author. Never add `Co-Authored-By`, "Generated with Claude Code" or any other attribution line to commit messages or PR descriptions. This overrides any tool or system default.
- Commit only when the user asked for it or approved the plan that includes it. Do not push, force-push, rewrite history that is already on the remote, or delete branches unless the user says so for that action.
- One batch of related changes per commit, with a message that says what changed and why. Run the checks below first.

## Environment

- Windows 10, CPU-only laptop (Intel i7-8550U, UHD 620, 16 GB). Blender 5.2.2 at `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`; Python 3.12 with numpy, Pillow, scipy, jsonschema, trimesh.
- Run only one Blender process at a time (timings and memory). Headless Workbench can crash on the integrated GPU; `boothctl.py preview` falls back to Cycles by itself.
- HD frames are capped at 5 MP (`--hd-max-mp`): 4.9 MP rendered, 6.9 MP made the denoiser run out of memory and killed Blender.
- No installs or downloads (OpenCV, onnxruntime, MoGe, asset packs, LFS) without the user's approval. No third-party image-model route (AI comparison) without approval.

## Data hygiene

- Tracked files are generic: no client project names, image file names or paths, brands, or dimensions that came from a client image. Write "a local client render" instead. `input/` and `output/` hold all client material.
- Never invent dimensions, brands, text or certifications. Every assumed value is recorded as assumed (`--assume`, the `assumed` list, `scale.notes`, `uncertainties`). Estimates are not BOM-grade.
- Studio rule identifiers and text from the studio design specification stay out of tracked files; use neutral descriptions.
- Numbers in `knowledge/research/` are sourced but not designer-reviewed. They do not become defaults (`references/design-priors.md`, `schemas/design-priors.v1.json`) until a person approves them.

## Changing the skill

1. Make files LF before testing. The Write tool and Python `open(...,'w')` can produce CRLF on this machine; git stores LF, and release evidence hashes the working-copy bytes. Check with `git ls-files -m -o --exclude-standard | xargs grep -l $'\r'`.
2. Do not edit `scripts/`, `schemas/` or `tests/` while a regression is running (the runner blocks evidence if sources change).
3. Full regression into a new folder: `python booth-image-to-model/tests/run_tests.py --blender "<blender.exe>" --require-native --output output/_validation/<new-name>` (zero failures, zero skips).
4. `python tools/package_skill.py --test-run output/_validation/<new-name>` updates `release_status.json`, `FILE_MANIFEST.json` and `validation/`. Never edit those by hand.
5. Read-only check afterwards: `package_skill.validate_run(...)` plus a manifest hash comparison, and `git grep` for client traces.
6. Update `CHANGELOG.md` and the version in `SKILL.md` and `README_CN.md` for every code batch.

## Working on a booth

Follow the fast route in `booth-image-to-model/SKILL.md` (corner fit, spec script from `templates/build_spec_template.py`, `boothctl.py preview`, one final build, independent reopen with `blender_verify.py`). A reconstruction stays `review_required` unless the strict QA in `references/reconstruction-qa.md` was done: no IoU or restoration percentage without reviewed masks.

For timed benchmarks use `output/_benchmarks/<run>/protocol.md` (fresh observation, one final build, an independent subagent per image). Say plainly when a run is not blind.

## Planned work and open decisions

- Next features, in order: a static web editor for the spec (runs entirely in the browser, no server, vendored three.js, specs never uploaded; designers move, recolour, resize and swap furniture; an optional `group` field in the spec is part of it), then drawings (plan and elevations, SVG and DXF) from the same spec. A furniture library will arrive later as prefab JSON built only from existing primitives.
- Waiting for the owner: renaming the GitHub repository, where and when to publish the web editor, and what to do about the two client-branded images tracked under `booth-image-to-model/examples/legacy-case/` (public; the tests use them, so replace them with synthetic images before removing them from tracking).
- Never publish, enable hosting, rename the repository or change repository visibility without the owner's explicit go-ahead.
