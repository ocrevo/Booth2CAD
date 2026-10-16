# Sample pictures (placeholders, to be replaced)

The showcase and demo pictures in the repository are **synthetic placeholders**: Blender renders and screenshots of the invented demo
booth (`web/tools/make_demo.py`). They will be replaced by **representative, free-to-use** booth pictures. This note records where
the pictures are used and what a replacement must satisfy, so they can be swapped in one batch.

## Where the pictures are used

| File | Used by | What it shows now |
|---|---|---|
| `docs/images/studio-demo.png` | `README.md`, `README.zh-CN.md` (top), `web/README.md`, GitHub social preview (`docs/github-settings.md`) | the studio with the demo booth: picture on the left, model on the right |
| `docs/images/editor-demo.png` | `web/README.md` (standalone editor) | the standalone editor with the demo booth |
| `web/app/demo/demo_source.png` | **试用示例展台** ("try the demo booth") in the studio | a Blender render of the demo booth from the demo camera |
| `web/app/demo/demo-booth.spec.json` | the demo in the studio and the standalone editor | the synthetic demo model; its `source` (size, sha256) belongs to `demo_source.png` |

If `demo_source.png` is missing, the studio shows the demo model on a plain stand-in picture and the tests make their own stand-in, so
the picture can be removed or replaced without breaking anything. Not affected: `booth-image-to-model/examples/regression/` holds
generated test fixtures (`tests/make_regression_example.py`), not samples.

## Requirements for a replacement

- **Licence:** your own picture with written permission from the stand owner and the photographer, or a public licence that allows
  redistribution and modification (CC0, CC BY 4.0, or similar). Record the source URL, author, licence and date in
  `THIRD_PARTY_NOTICES.md` (attribution text for CC BY). No "free to view" pictures, stock pictures with restrictive terms, or
  pictures copied from exhibitor or venue websites.
- **Content:** a typical exhibition stand (for example an island or a corner stand) with clear corners and floor edges, as a render
  or a real photo. No identifiable people, or people with consent; no trademarks or logos that are the subject of the picture; no
  client projects.
- **File:** PNG or JPEG, at most 5 MP, no EXIF rotation (the studio refuses both), metadata stripped (`python -c "from PIL import Image;
  Image.open('in.jpg').save('out.png')"` drops EXIF), descriptive alt text where it is shown (`tools/check_docs.py` checks alt text).

## Replacing them

1. Showcase: overwrite `docs/images/studio-demo.png` and `docs/images/editor-demo.png` (or add new files and update the links), take
   the screenshots from the studio and editor with the new demo loaded, and update the alt text and captions in the READMEs.
2. Demo: replace `web/app/demo/demo_source.png`, then build its model with the studio or the skill (corner fit, scene description,
   compile), check it with `validate_spec.py --check-source`, and save it as `web/app/demo/demo-booth.spec.json`. `make_demo.py` only
   builds the synthetic booth; the studio smoke test expects the demo's part count, so update that number too.
3. Set the social preview, add the attributions, and run `python tools/check_docs.py`, `npm test`, `npm run smoke` and
   `npm run smoke:studio`.
