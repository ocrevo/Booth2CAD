# Booth spec editor

A static, client-side editor for a `booth-image-to-model` spec (`spec.json`). Designers can move, turn, recolour, resize
and duplicate parts; the edited spec is saved as a normal `spec.json` and is checked by the same Python validator.
In this static mode everything runs in the browser: no server, no login, nothing is uploaded. The same page also works as the
editor step of the studio (below), where it talks only to the local studio server.

## Try it (test page)

```
python web/tools/serve.py          # serves web/app on http://127.0.0.1:8000/ and opens the browser
```

Opening `index.html` by double-click does not work (browsers refuse ES modules from `file://`).
The page loads a synthetic demo booth (invented for testing, no client data). The "测试指引 / Test guide" button lists
what to try. Use "Open spec" or drop a `spec.json` on the page to edit your own.

## Studio: the whole flow on one page

```
python web/server/run.py           # http://127.0.0.1:8800/  (the flow page; opens the browser)
```

Picture -> reading -> compile -> preview -> edit -> build -> open in Blender, one card per step, each with its state, result and
error. Jobs live in `output/studio/<id>/` (git-ignored). Only the Python standard library is needed besides the skill's own
requirements; Blender is found through `BLENDER_EXE`, `PATH` or the default install path (without it GLB export still works).

| Step | What happens | Needs |
|---|---|---|
| 1 Picture | PNG or JPEG is stored in the job | |
| 2 Reading | one of: upload a scene description (`references/scene-description.md`), upload a ready spec (its picture hash must match), or let OpenAI read the picture | key + consent for OpenAI |
| 3 Compile | scene description -> camera fit -> spec, with fit residuals, dropped parts, assumptions and an overlay | |
| 4 Preview | Blender renders a comparison sheet at the source camera | Blender |
| 5 Edit | `index.html?job=<id>` loads the job's spec; "保存到工作区" validates it and marks later steps stale | |
| 6 Build | `.blend`, client render, GLB | Blender (GLB: none) |
| 7 Open | opens the latest `.blend` in Blender; downloads for every file | Blender |

**OpenAI (optional).** Set `OPENAI_API_KEY` before starting, or paste the key on the page (kept in the server's memory, never written
to disk or to the job). The picture is sent only after the consent box is ticked for that job. `OPENAI_MODEL` (default `gpt-5.5`),
`OPENAI_BASE_URL`, `OPENAI_API_STYLE` (`responses`, or `chat` for OpenAI-compatible services such as DeepSeek or a local vLLM) and
`OPENAI_REASONING_EFFORT` configure it; there is no SDK, the call is plain HTTP in `server/reader_openai.py`. The reply is checked
with the same validator the compiler uses and sent back for at most two repairs. Without a key every other step works.

**Limits and safeguards.** Pictures are PNG or JPEG up to 25 MB and 5 MP: Blender renders at the picture's size and a larger frame
ran the denoiser out of memory. A picture with an EXIF rotation tag (common for phone photos) is refused, because the browser shows
it upright while the pixels are sideways; save it again without the tag. `OPENAI_MAX_OUTPUT_TOKENS` (default 32000) must not exceed
what the model or service accepts. A job refuses edits and uploads while one of its steps runs. "Run everything" continues from the
current state: it never recompiles over a spec you edited or uploaded, and the compile button asks before overwriting an edited spec.
After a server restart, steps that were running show as errors and queued ones return to their earlier state. A second copy cannot
start on the same port, and requests from other web pages (wrong Host or Origin) are refused.

Local only: the server listens on `127.0.0.1`, the page talks to nothing else, and the static site (`app/`) never receives a key
or a picture. Reading quality is the weak point of this first version; the compile step shows the fit residuals and the overlay so a
bad reading is visible before anything is built.

## Layout

| Folder | What | Served? |
|---|---|---|
| `app/` | the site: `flow.html` (studio), `index.html` (editor), `js/`, `css/`, `vendor/three/`, `demo/` | yes, this is the deploy root |
| `server/` | the local studio server: `run.py`, `server.py` (HTTP), `jobs.py`, `steps.py`, `engine.py` (the only file that touches the skill), `reader_openai.py`, `grid.py`, `prompts/` | no |
| `tests/` | `node --test` suites, Python server/reader tests, a stand-in for the OpenAI API, end-to-end smoke tests | no |
| `tools/` | `serve.py` (static preview server), `make_demo.py` (rebuilds the demo spec from the skill's macros) | no |

Deploy only `app/` for the static editor. Tests, tools and the server stay out of whatever gets published. The server depends on the
skill (`booth-image-to-model/`) and the skill does not know the web folder exists.

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
npm run smoke       # headless Chrome/Edge drives the editor in static mode (needs Chrome or Edge and Python)
npm run test:server # Python: every studio step through the real HTTP API, the OpenAI reader against a stand-in server
                    # (set BLENDER_EXE to include the preview/build steps)
npm run smoke:flow  # headless Chrome drives the flow page end to end, with the stand-in for OpenAI (Blender steps if found)
python tests/make_geometry_reference.py   # regenerate the Python reference data after changing geometry.py
python tools/make_demo.py                 # rebuild app/demo after changing the macros
```

## Limits (first version)

Grid patterns and text are drawn schematically; orthographic cameras are not supported; there is no furniture library yet
(duplicate existing pieces); principal-point shifts are applied but lens distortion is not modelled.

## Third-party

three.js 0.186.1 (MIT) is vendored unmodified under `app/vendor/three/` (see `VERSION.txt` and `LICENSE` there).
