from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs' / 'assets' / 'readme'
OUTPUT = ROOT / 'artifacts' / 'submission_materials' / 'jpg'
NAMES = [
    'app_decision_workbench.png', 'app_overview.png', 'case33bw_topology.png',
    'claim_gates.png', 'gridrescue_architecture.png', 'streamlit_tabs.png',
    'wave10_01_strategy_comparison.png', 'wave10_02_inventory_breakdown.png',
    'wave10_03_physics_voltage_gate.png', 'wave10_04_action_timeline.png',
    'wave10_05_pareto_controlled_service.png', 'wave10_06_mrv_reconciliation.png',
    'wave10_07_caretask_contracts.png',
]


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        image = Image.open(SOURCE / name).convert('RGB')
        image.save(OUTPUT / (Path(name).stem + '.jpg'), format='JPEG', quality=95, optimize=True, subsampling=0)
    print(f'converted={len(NAMES)} output={OUTPUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
