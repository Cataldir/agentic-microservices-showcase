"""Run deterministic book-support tests; print portable evidence without host paths."""
from pathlib import Path
import io
import json
import platform
import sys
import time
import unittest


def main():
    repository = Path(__file__).resolve().parents[2]
    suite = unittest.defaultTestLoader.discover(
        str(repository / "tests" / "book_examples"), top_level_dir=str(repository))
    output = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    report = {
        "python": platform.python_version(),
        "command": "python -m core.book_examples.verify",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "classification": "deterministic local teaching models and printed/full parity",
        "external_integrations_executed": [],
        "no_installation": True,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["successful"]:
        print(output.getvalue(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
