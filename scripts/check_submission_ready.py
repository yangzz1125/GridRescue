from __future__ import annotations

import argparse
import os
import json
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT.parents[1] / "outputs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check GridRescue submission readiness")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--run-smoke", action="store_true")
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    required = [
        "app.py",
        "docs/10_day_execution_plan.md",
        "docs/final_submission_checklist.md",
        "docs/final_goal_audit.md",
        "docs/team_recruitment_brief.md",
        "docs/solo_operator_plan.md",
        "docs/demo_audit_wave11.md",
        "docs/teammate_onboarding.md",
        "docs/official_competition_facts_2026.md",
        "artifacts/submission_materials/README_media.md",
        "artifacts/submission_materials/GridRescue_赛道2_项目申报书.pdf",
        "artifacts/submission_materials/GridRescue_demo_preview.mp4",
        "artifacts/submission_materials/GridRescue_demo_narrated_ai_preview.mp4",
        "artifacts/wave10/strict_contract_9/strict_contract_manifest.json",
        "artifacts/wave11/risk_report/risk_report.json",
        "artifacts/wave11/mrv_sensitivity/sensitivity_report.json",
    ]
    checks.update({f"file:{item}": (ROOT / item).is_file() for item in required})
    preview = ROOT / "artifacts" / "submission_materials" / "GridRescue_demo_preview.mp4"
    checks["media:pdf_under_40mb"] = (ROOT / "artifacts" / "submission_materials" / "GridRescue_赛道2_项目申报书.pdf").stat().st_size < 40 * 1024 * 1024 if (ROOT / "artifacts" / "submission_materials" / "GridRescue_赛道2_项目申报书.pdf").exists() else False
    checks["media:mp4_under_200mb"] = preview.stat().st_size < 200 * 1024 * 1024 if preview.exists() else False
    narrated = ROOT / "artifacts" / "submission_materials" / "GridRescue_demo_narrated_ai_preview.mp4"
    checks["media:narrated_mp4_under_200mb"] = narrated.stat().st_size < 200 * 1024 * 1024 if narrated.exists() else False
    audit_env = os.environ.copy()
    audit_env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + audit_env.get("PYTHONPATH", "")
    claim_audit = subprocess.run([sys.executable, "scripts/audit_claims.py"], cwd=ROOT, env=audit_env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    checks["claim_audit"] = claim_audit.returncode == 0
    package_candidates = [
        ROOT / "release" / "GridRescue_Wave11_P1_Submission.zip",
        OUTPUTS / "GridRescue_Wave11_P1_Submission.zip",
    ]
    package = next((candidate for candidate in package_candidates if candidate.is_file()), package_candidates[-1])
    checks["package:exists"] = package.is_file()
    if package.is_file():
        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
            checks["package:testzip"] = archive.testzip() is None
            checks["package:single_manifest"] = names.count("release_manifest_wave11_submission.json") == 1
            checks["package:goal_audit"] = "docs/final_goal_audit.md" in names
            checks["package:demo_audit"] = "docs/demo_audit_wave11.md" in names
            checks["package:teammate_onboarding"] = "docs/teammate_onboarding.md" in names
            checks["package:submission_pdf"] = "artifacts/submission_materials/GridRescue_赛道2_项目申报书.pdf" in names
            checks["package:submission_media"] = sum(name.startswith("artifacts/submission_materials/jpg/") and name.lower().endswith(".jpg") for name in names) >= 13
            checks["package:demo_preview"] = "artifacts/submission_materials/GridRescue_demo_preview.mp4" in names
            checks["package:demo_narrated_preview"] = "artifacts/submission_materials/GridRescue_demo_narrated_ai_preview.mp4" in names
            checks["package:smoke_script"] = "scripts/smoke_demo.py" in names
    else:
        checks.update({"package:testzip": False, "package:single_manifest": False, "package:goal_audit": False, "package:demo_audit": False, "package:teammate_onboarding": False, "package:submission_pdf": False, "package:submission_media": False, "package:demo_preview": False, "package:demo_narrated_preview": False, "package:smoke_script": False})
    if args.run_tests:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
        checks["pytest"] = result.returncode == 0
    if args.run_smoke:
        result = subprocess.run([sys.executable, "scripts/smoke_demo.py"], cwd=ROOT)
        checks["streamlit_smoke"] = result.returncode == 0
    payload = {"checks": checks, "passed": all(checks.values()), "failed": [key for key, value in checks.items() if not value]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
