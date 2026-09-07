from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
    files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".md", ".py", ".yaml", ".csv", ".json"}
        and "__pycache__" not in p.parts
        and ".pytest_cache" not in p.parts
        and "research_wave" not in p.parts
        and "scripts" not in p.parts
    ]
    failed = False
    for pattern in PATTERNS:
        hits = []
        for path in files:
            for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern in line:
                    hits.append(f"{path.relative_to(ROOT)}:{line_no}:{line[:180]}")
        print(f"--- {pattern} ({len(hits)}) ---")
        for hit in hits[:20]:
            print(hit)
        if pattern in {"kgCO2e", "CO₂e", "28 passed", "11 files"} and hits:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
