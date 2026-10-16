// Run Python the same way on every OS (used by the npm scripts): $PYTHON, else `python` on Windows and `python3` elsewhere.
//   node tools/py.mjs <python arguments...>

import { spawnSync } from 'node:child_process';
import { PYTHON } from '../tests/python.mjs';

const result = spawnSync(PYTHON, process.argv.slice(2), { stdio: 'inherit' });
if (result.error) {
  console.error(`cannot run "${PYTHON}": ${result.error.message}. Install Python 3.10+ or set PYTHON to its path.`);
  process.exit(2);
}
process.exit(result.status ?? 1);
