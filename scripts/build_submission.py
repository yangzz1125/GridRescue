from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT.parents[1] / "outputs"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_files() -> list[tuple[Path, Path]]:
    selected: list[tuple[Path, Path]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        parts = set(relative.parts)
        rel_text = relative.as_posix()
        if "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        # The desktop `release/` directory is a delivery mirror, not project
        # source.  Excluding it prevents recursive self-inclusion of the
        # previous ZIP/SHA files when rebuilding a submission package.
        if "release" in parts:
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if "research_wave" in parts or rel_text.startswith("outputs/"):
            continue
        # Keep large raw public-data archives in the local evidence workspace,
        # but ship only the small derived sample and metadata in the contest ZIP.
        if rel_text.startswith("data/outage/raw/"):
            continue
        if rel_text.startswith("artifacts/") and not (
            rel_text.startswith("artifacts/v08_official/")
            or rel_text.startswith("artifacts/wave10/catalog/")
            or rel_text.startswith("artifacts/wave10/figures/")
            or rel_text.startswith("artifacts/wave10/pipeline_cache/")
            or rel_text.startswith("artifacts/wave10/batch36/")
              or rel_text.startswith("artifacts/wave10/c0_c4_gate/")
              or rel_text.startswith("artifacts/wave10/strict_contract_demo/")
              or rel_text.startswith("artifacts/wave10/strict_contract_9/")
              or rel_text.startswith("artifacts/wave11/risk_report/")
              or rel_text.startswith("artifacts/wave11/mrv_sensitivity/")
              or rel_text.startswith("artifacts/submission_materials/")
          ):
            continue
        if relative.name.startswith("release_manifest_"):
            continue
        # Internal blind-review notes are useful during preparation but are
        # not part of the anonymous competition submission package.
        if relative.name == "blind_judge_review_wave11.md" or relative.name.endswith(".bak_blindreview"):
            continue
        selected.append((relative, path))
    return sorted(selected, key=lambda item: item[0].as_posix())


def main() -> int:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    files = selected_files()
    manifest = {
        "schema_version": "gridrescue-wave11-submission-manifest-1.0",
        "project": "GridRescue 碳韧智网",
        "release": "Wave11-P1-Submission",
        "generated_at": "2026-08-27",
        "v08_freeze_date": "2026-08-22",
        "tests": {"command": "python -m pytest -q", "passed": 78, "v08_baseline_passed": 46},
        "claim_boundary": {
            "gas_basis": "CO2",
            "unit": "kgCO2",
            "factor_data_class": "E",
            "time_step_h": 1.0,
            "same_service_pass": False,
            "claim_status": "controlled_service_budget_inventory_difference",
            "seal_meaning": "File integrity and internal recomputation only; not field measurement or third-party assurance.",
        },
        "deliverables": [
            "评委决策工作台",
            "三门证据与NO_GFM反例预设",
            "36条可重放场景catalog",
            "paired统计基础函数",
            "V08正式MRV证据包",
        ],
        "files": [
            {"path": rel.as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
            for rel, path in files
        ],
    }
    manifest_path = ROOT / "release_manifest_wave11_submission.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    files.append((manifest_path.relative_to(ROOT), manifest_path))
    files.sort(key=lambda item: item[0].as_posix())

    archive_path = OUTPUTS / "GridRescue_Wave11_P1_Submission.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, path in files:
            archive.write(path, relative.as_posix())
    archive_hash = sha256(archive_path)
    (OUTPUTS / "GridRescue_Wave11_P1_Submission_SHA256.txt").write_text(
        f"{archive_hash}  {archive_path.name}\n", encoding="utf-8"
    )
    with zipfile.ZipFile(archive_path) as archive:
        corrupt = archive.testzip()
    print(
        json.dumps(
            {
                "archive": str(archive_path),
                "sha256": archive_hash,
                "files": len(files),
                "bytes": archive_path.stat().st_size,
                "testzip": corrupt,
            },
            ensure_ascii=False,
        )
    )
    return 0 if corrupt is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
