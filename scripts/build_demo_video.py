from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = Path(r"C:\Users\ASUS\Documents\ffmpeg-6.0-essentials_build\bin\ffmpeg.exe")

SLIDES = [
    ("app_decision_workbench.png", 30),
    ("case33bw_topology.png", 25),
    ("wave10_01_strategy_comparison.png", 30),
    ("wave10_03_physics_voltage_gate.png", 30),
    ("wave10_05_pareto_controlled_service.png", 35),
    ("claim_gates.png", 30),
    ("wave10_06_mrv_reconciliation.png", 35),
    ("wave10_07_caretask_contracts.png", 30),
    ("app_overview.png", 25),
    ("gridrescue_architecture.png", 25),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a 4:55 silent visual demo preview from GridRescue figures")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "submission_materials" / "GridRescue_demo_preview.mp4")
    args = parser.parse_args()
    ffmpeg = FFMPEG if FFMPEG.exists() else Path(shutil.which("ffmpeg") or "")
    if not ffmpeg.exists():
        raise FileNotFoundError("ffmpeg executable not found")
    source = ROOT / "docs" / "assets" / "readme"
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gridrescue_video_") as tmp:
        concat = Path(tmp) / "slides.txt"
        lines: list[str] = []
        for filename, duration in SLIDES:
            image = (source / filename).resolve()
            if not image.exists():
                raise FileNotFoundError(image)
            escaped = str(image).replace("'", "'\\''")
            lines.extend([f"file '{escaped}'", f"duration {duration}"])
        # concat demuxer needs the final file repeated to honor the final duration.
        escaped = str((source / SLIDES[-1][0]).resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = [
            str(ffmpeg), "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0b1c25,format=yuv420p",
            "-r", "30", "-t", "295", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-movflags", "+faststart", str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if result.returncode != 0 or not output.exists():
            raise RuntimeError(f"ffmpeg failed rc={result.returncode}\n{result.stderr[-2000:]}")
    print(f"output={output}")
    print(f"bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
