import subprocess
import sys
from pathlib import Path


def test_e2e_sidecar_offline_eval_script_runs():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "e2e_sidecar_offline_eval.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "E2E_OK" in result.stdout
    assert "overall_score" in result.stdout
