# Sample pictures (to be chosen)

The repository has no showcase or demo picture for now. The earlier ones were synthetic Blender renders and screenshots; they were
left out so that the project can show **representative, free-to-use** booth pictures instead. This note records where pictures are
needed and what they must satisfy, so they can be added in one batch.

## Where pictures are needed

| Place | What it shows | Now |
|---|---|---|
| `README.md`, `README.zh-CN.md` (top) | The studio: a booth picture next to its rebuilt, editable model at the same camera | an HTML comment marks the spot |
| `web/README.md` (studio and standalone editor sections) | The studio with a job open; the standalone editor with a model | removed |
| GitHub social preview (`docs/github-settings.md`) | One picture, cropped to 1280 × 640 | not set |
| `web/app/demo/demo_source.png` | The picture behind **试用示例展台** ("try the demo booth") | git-ignored; the studio shows the demo model on a plain stand-in |
| `web/app/demo/demo-booth.spec.json` | The demo model; it must belong to the demo picture (same frame size, camera fitted to it) | synthetic model, made by `web/tools/make_demo.py` |

Not affected: `booth-image-to-model/examples/regression/` holds generated test fixtures (`tests/make_regression_example.py`), not
samples.

## Requirements for each picture

- **License:** your own picture with written permission from the stand owner and the photographer, or a public licence that allows
  redistribution and modification (CC0, CC BY 4.0, or similar). Record the source URL, author, licence and date in
  `THIRD_PARTY_NOTICES.md` (attribution text for CC BY). No "free to view" pictures, stock pictures with restrictive terms, or
  pictures copied from exhibitor or venue websites.
- **Content:** a typical exhibition stand (for example an island or a corner stand) with clear corners and floor edges, as a render
  or a real photo. No identifiable people, or people with consent; no trademarks or logos that are the subject of the picture; no
  client projects.
- **File:** PNG or JPEG, at most 5 MP, no EXIF rotation (the studio refuses both), metadata stripped (`python -c "from PIL import Image;
  Image.open('in.jpg').save('out.png')"` drops EXIF), descriptive alt text where it is shown (`tools/check_docs.py` checks alt text).

## Adding them

1. Put the pictures under `docs/images/` (showcase) and `web/app/demo/demo_source.png` (demo), and remove the demo picture's line from
   `.gitignore`.
2. For a real demo picture, build its model with the studio or the skill (corner fit, scene description, compile), check it with
   `validate_spec.py --check-source`, and save it as `web/app/demo/demo-booth.spec.json`; `make_demo.py` only builds the synthetic
   booth.
3. Restore the images in the READMEs, set the social preview, add the attributions, and run `python tools/check_docs.py`, `npm test`,
   `npm run smoke` and `npm run smoke:studio`.
