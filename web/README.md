# Booth spec editor

A static, client-side editor for a `booth-image-to-model` spec (`spec.json`). Designers can move, turn, recolour, resize
and duplicate parts; the edited spec is saved as a normal `spec.json` and is checked by the same Python validator.
Everything runs in the browser. No server, no login, nothing is uploaded.

## Try it (test page)

```
python web/tools/serve.py          # serves web/app on http://127.0.0.1:8000/ and opens the browser
```

Opening `index.html` by double-click does not work (browsers refuse ES modules from `file://`).
The page loads a synthetic demo booth (invented for testing, no client data). The "测试指引 / Test guide" button lists
what to try. Use "Open spec" or drop a `spec.json` on the page to edit your own.

## Layout

| Folder | What | Served? |
|---|---|---|
| `app/` | the site: `index.html`, `js/`, `css/`, `vendor/three/`, `demo/` | yes, this is the deploy root |
| `tests/` | `node --test` suites, Python reference data, end-to-end smoke test | no |
| `tools/` | `serve.py` (local server), `make_demo.py` (rebuilds the demo spec from the skill's macros) | no |

Deploy only `app/`. Tests and tools stay out of whatever gets published.

## How it works

- The spec is the single source of truth. `js/spec.js` holds pure edit operations (move, yaw about the vertical axis,
  uniform scale, duplicate, delete, group, material) with rollback when a part no longer builds, plus a light validation
  that mirrors `validate_spec.py` (the Python validator stays authoritative).
- `js/geometry.js` is a line-for-line port of `booth-image-to-model/scripts/geometry.py`; parity tests compare vertex
  and face counts, bounding boxes, areas, volumes and refusals against the Python builders.
- `js/camera.js` reproduces `camera_math.py` ("Match source view"); tests compare projected pixels with Python.
- Z is up everywhere (the spec's axes). Euler angles use Blender's order, which is three.js `ZYX`.
- Edited parts are marked `inferred` with the note "Edited in the web editor"; the fitted camera is marked `unfitted`.
  Parts that share a `group` are selected, moved, turned, scaled and duplicated together.
- Floor size edits keep `scale.footprint_m` equal to the floor, as the validator requires.
- GLB export: one node per part named by component id, `group:<name>` parents, spec metadata as extras, Y-up.

## Checks

```
cd web
npm test            # node --test: geometry/camera parity with Python, edit operations, Python round trip
npm run smoke       # headless Chrome/Edge drives the real page (needs Chrome or Edge and Python)
python tests/make_geometry_reference.py   # regenerate the Python reference data after changing geometry.py
python tools/make_demo.py                 # rebuild app/demo after changing the macros
```

## Limits (first version)

Grid patterns and text are drawn schematically; orthographic cameras are not supported; there is no furniture library yet
(duplicate existing pieces); principal-point shifts are applied but lens distortion is not modelled.

## Third-party

three.js 0.186.1 (MIT) is vendored unmodified under `app/vendor/three/` (see `VERSION.txt` and `LICENSE` there).
