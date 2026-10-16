## What and why

<!-- One topic per pull request. -->

## Checklist

- [ ] No client pictures, brand names, project names, client file names or client-derived dimensions in tracked files
- [ ] `python tools/check_lf.py` and `python tools/check_docs.py` pass
- [ ] The checks that touch this change pass (see CONTRIBUTING.md): skill tests / `npm test` / `npm run test:server` / smoke tests
- [ ] Skill changes (`booth-image-to-model/scripts`, `schemas`, `tests`) have a `CHANGELOG.md` entry; release evidence files were not edited by hand
- [ ] No new dependency (or it was agreed in an issue first)
