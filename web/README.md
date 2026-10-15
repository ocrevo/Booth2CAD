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

## Studio: from picture to render in one window

```
python web/server/run.py           # http://127.0.0.1:8800/  (opens the browser)
```

One page, four steps in a bar at the top: **① 选图 → ② 生成模型 → ③ 调整 → ④ 出图**. The stage in the middle is always the same
place: the empty drop zone, then the picture, then the model drawn over the picture at the picture's own camera. The right-hand card
always says the one thing to do next (and what is running, how long it has taken and usually takes, or what failed and the one
button to try again). Nothing opens in another window.

| Step | What the person does | What happens underneath |
|---|---|---|
| ① 选图 | drops or chooses a PNG or JPEG | the picture is stored in the job (`output/studio/<id>/`, git-ignored) |
| ② 生成模型 | ticks the consent, clicks "生成模型" (or "生成并直接出图"); "更多方式" holds the uploads and the key | a large model reads the picture, the engine fits the camera and builds the model (steps `scene`, `compile`) |
| ③ 调整 | clicks, drags, recolours on the stage; compares with the photo (wipe / overlay / photo alone / model; hold Space to peek) | every change is saved by itself 0.8 s later ("已保存 ✓") |
| ④ 出图 | "出图（1–3 分钟）"; optionally "先快速校对（约 15 秒）" first | Blender renders the client picture and the server writes the `.glb` (steps `build`, `glb`); downloads and "在 Blender 中打开" appear |

The conclusion on the card is in plain words (model ready / may not line up with the photo, by how many pixels / sizes estimated).
The engineering view is behind **专业视图** (a drawer): the fit overlay, the corner-error table, the Blender check sheet, what was
dropped or assumed, the design-check hints, every step's record and log. The editor itself (`js/app.js`, `createEditor`) is hosted in
the stage; the standalone `index.html` still works without a server and uploads nothing.

Before/after never needs another Blender run: the live model is drawn by three.js at the matched camera (labelled as schematic),
a quick check shows `preview_render.png`, a finished render shows `client_render.png` (wipe) or `reference_render.png` (transparent,
overlay). A render goes stale when the model changes afterwards and is then said to be stale, never silently shown as current.
Jobs need only the Python standard library besides the skill's own requirements; Blender is found through `BLENDER_EXE`, `PATH` or the
default install path (without it the journey stops before the render and the `.glb` can still be exported).

**Reading with a large model (optional).** Any OpenAI-compatible service works; there is no vendor SDK, the call is plain HTTP in
`server/reader_openai.py`. The key goes in the environment variable `OPENAI_API_KEY` (whichever service it belongs to) before starting,
or is pasted on the page (step ②), where it is kept in the server's memory and never written to disk or
to a job. The picture is sent only after the consent box is ticked for that job.

```
python web/server/run.py                          # OpenAI: Responses API, model gpt-5.5, strict JSON schema
python web/server/run.py --provider deepseek      # DeepSeek: https://api.deepseek.com, model deepseek-flash, JSON mode
```

A provider preset sets base URL, model and request style; `--openai-base-url`, `--openai-model`, `--openai-style` (or `OPENAI_BASE_URL`,
`OPENAI_MODEL`, `OPENAI_API_STYLE`) override it. Styles: `responses` (OpenAI Responses API), `chat` (Chat Completions with a strict
schema), `chat-json` (Chat Completions for services that only have JSON mode, as DeepSeek: the schema is written into the instructions
and the local validator plus up to two repair turns enforce it). `OPENAI_REASONING_EFFORT` (e.g. `none` to switch thinking off where the
service supports it) and `OPENAI_MAX_OUTPUT_TOKENS` tune the request. The reply is checked with the same validator the compiler uses.
Every request and reply of a reading is kept in the job's `reader/` folder (pictures and the key are not). Without a key every other
step works.

**Limits and safeguards.** Pictures are PNG or JPEG up to 25 MB and 5 MP: Blender renders at the picture's size and a larger frame
ran the denoiser out of memory. A picture with an EXIF rotation tag (common for phone photos) is refused, because the browser shows
it upright while the pixels are sideways; save it again without the tag. `OPENAI_MAX_OUTPUT_TOKENS` (default 32000) must not exceed
what the model or service accepts. A job refuses edits and uploads while one of its steps runs. "Run everything" continues from the
current state: it never rebuilds the model over one you edited or uploaded, and an edit made while a step runs is saved as soon as it ends.
After a server restart, steps that were running show as errors and queued ones return to their earlier state. A second copy cannot
start on the same port, and requests from other web pages (wrong Host or Origin) are refused.

Local only: the server listens on `127.0.0.1`, the page talks to nothing else, and the static site (`app/`) never receives a key
or a picture. Reading quality is the weak point of this first version; the compile step shows the fit residuals and the overlay so a
bad reading is visible before anything is built.

## Layout

| Folder | What | Served? |
|---|---|---|
| `app/` | the site: `studio.html` (the studio), `index.html` (the standalone editor), `js/`, `css/`, `vendor/three/`, `demo/` | yes, this is the deploy root |
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
npm run smoke:studio # headless Chrome drives the studio end to end in one window, with the stand-in for OpenAI (Blender steps if found)
python tests/make_geometry_reference.py   # regenerate the Python reference data after changing geometry.py
python tools/make_demo.py                 # rebuild app/demo after changing the macros
```

## Limits (first version)

Grid patterns and text are drawn schematically; orthographic cameras are not supported; there is no furniture library yet
(duplicate existing pieces); principal-point shifts are applied but lens distortion is not modelled.

## Third-party

three.js 0.186.1 (MIT) is vendored unmodified under `app/vendor/three/` (see `VERSION.txt` and `LICENSE` there).
