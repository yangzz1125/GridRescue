from __future__ import annotations

from pathlib import Path
import sys

from gridrescue.facts import validate_text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PATTERNS = (
    "kgCO2e",
    "CO₂e",
    "严格同服务减排",
    "同服务减排",
    "28 passed",
    "11 files",
    "冰灾",
    "实时控制",
    "现场实测",
    "第三方核证",
)


def main() -> int:
    # Keep claim audit usable from PowerShell consoles with a legacy code page.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".md", ".yaml", ".csv", ".json"}
        and "__pycache__" not in p.parts
        and ".pytest_cache" not in p.parts
        and "research_wave" not in p.parts
        and "scripts" not in p.parts
        and "tests" not in p.parts
        and "src" not in p.parts
    ]
    failures: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        errors = validate_text(text)
        for error in errors:
            failures.append(f"{path.relative_to(ROOT)}: {error}")
    if failures:
        print("claim_audit=FAIL")
        for failure in failures:
            print(failure)
        return 1
    print(f"claim_audit=PASS files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
