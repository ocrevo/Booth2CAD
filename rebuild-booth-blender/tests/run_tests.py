"""Run tests and write a machine-readable record; preserve skipped test labels."""
from pathlib import Path
import sys
import unittest
import json
import platform
ROOT=Path(__file__).resolve().parents[1]
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
summary={'tests_run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
         'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],
         'skipped':[(str(t),s) for t,s in result.skipped],'python':platform.python_version(),
         'all_executed_tests_passed':result.wasSuccessful(),
         'scope':'Unit tests, real legacy-input rejection and synthetic camera/geometry tests. Not a completed Legacy case image reconstruction.'}
(ROOT/'validation').mkdir(exist_ok=True)
(ROOT/'validation/test_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
