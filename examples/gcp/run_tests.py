"""Testes offline: doubles + JSON, sem SDK, autenticação ou instalação."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
stream = io.StringIO()
with patch("socket.socket", side_effect=AssertionError("Teste offline não pode abrir socket")) as sockets:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
output = stream.getvalue()
(ROOT / "test-output.txt").write_text(output, encoding="utf-8")
report = {
    "run_at_utc": datetime.now(timezone.utc).isoformat(),
    "python": sys.version.split()[0],
    "tests": result.testsRun,
    "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
    "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
    "passed_all": result.wasSuccessful() and not result.skipped and sockets.call_count == 0,
    "socket_attempts": sockets.call_count,
    "execution": "stdlib offline doubles; no sockets, SDK real, ADC, API activation or cloud resource",
    "terraform": "JSON parsed; invariants/references checked; Terraform CLI/provider validate/plan/apply NOT executed",
}
(ROOT / "test-results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(output, end="")
print(json.dumps(report, ensure_ascii=False))
raise SystemExit(0 if report["passed_all"] else 1)
