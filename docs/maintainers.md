# Maintainer notes

How a release of the skill is checked and recorded. Contributors do not need this; they run the checks in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Release evidence

`booth-image-to-model/` carries generated evidence of the last full native regression:

| File | What it is |
|---|---|
| `release_status.json` | Version, release status, what was tested natively, open limits |
| `FILE_MANIFEST.json` | SHA-256 of every tracked file of the skill, so a copy can be checked against a release |
| `validation/` | The last regression's results, logs and environment probe; `validation/history/` keeps earlier ones |
| `validation/audit_report.json` | Findings of the last independent audit and their resolution |

These files are **written only by `tools/package_skill.py`** and never edited by hand. They describe the machine that ran the
regression (Blender version, timings); they are not a statement that every machine behaves the same way, and they are not a visual
accuracy score for any picture.

## Releasing a change of the skill

1. Make text files LF: `python tools/check_lf.py`. (Some editors and Python's `open(..., 'w')` on Windows write CRLF; git stores LF
   and the evidence hashes the working-copy bytes.)
2. Do not edit `scripts/`, `schemas/` or `tests/` while a regression runs; the runner refuses evidence when sources change under it.
3. Full regression into a new folder, with Blender:

   ```bash
   python booth-image-to-model/tests/run_tests.py --blender "$BLENDER_EXE" --require-native --output output/_validation/<new-name>
   ```

   It must report zero failures and zero skips. `--require-native` blocks instead of skipping when Blender is missing.
4. Record it: `python tools/package_skill.py --test-run output/_validation/<new-name>`. This checks that the run matches the current
   sources, archives the previous evidence and rewrites `release_status.json`, `FILE_MANIFEST.json` and `validation/`.
5. Read-only check afterwards: `package_skill.validate_run(...)`, a comparison of `FILE_MANIFEST.json` with the working copy, and a
   search for private traces (client names, personal paths) with `git grep`.
6. Update `CHANGELOG.md` and the version in `SKILL.md` and `README_CN.md`.

## Timed benchmarks

For timed runs of the whole workflow on new pictures, keep a protocol under `output/_benchmarks/<run>/protocol.md` (fresh observation,
one final build, one independent agent per picture) and say plainly when a run was not blind. Pictures and results stay in the
git-ignored `output/`.

## Web product

The web studio and editor have no generated evidence. Before a release: `cd web && npm test && npm run test:server && npm run smoke &&
npm run smoke:studio` with Blender available, plus the same `smoke:studio` with `--image <picture> --scene <scene.json>` on a real
picture kept outside the repository.
