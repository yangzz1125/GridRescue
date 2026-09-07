"""Capture the pre-change environment and run the complete regression suite."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "competition2026" / "validation"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = OUT / "baseline.json"
    if baseline.exists():
        raise SystemExit("Baseline already exists; refusing to overwrite")
    files = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in {".py", ".toml", ".txt", ".md", ".csv", ".json", ".m", ".pkl"} and not any(x in p.parts for x in ("__pycache__", ".pytest_cache", ".pi", "competition2026"))]
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "git": "not a git repository; no branch or worktree",
        "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "networkx", "cvxpy", "clarabel", "streamlit", "plotly", "pytest")},
        "files": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
    }
    baseline.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "baseline_pytest.log").open("w", encoding="utf-8") as log:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    print(f"baseline={baseline} pytest_exit={result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
