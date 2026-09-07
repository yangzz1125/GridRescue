from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
EDGE_CANDIDATES = [
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

CSS = r"""
@page { size: A4; margin: 17mm 16mm 18mm 16mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; color: #1a2933; font-size: 10.5pt; line-height: 1.62; }
h1 { font-size: 21pt; color: #0b566b; border-bottom: 2px solid #26a69a; padding-bottom: 5mm; margin: 0 0 7mm; }
h2 { font-size: 15pt; color: #0b566b; border-left: 4px solid #26a69a; padding-left: 3mm; margin: 8mm 0 3mm; page-break-after: avoid; }
h3 { font-size: 12pt; color: #17495a; margin: 5mm 0 2mm; page-break-after: avoid; }
p { margin: 2.5mm 0; text-align: justify; }
ul, ol { margin-top: 2mm; margin-bottom: 3mm; }
li { margin: 1.2mm 0; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0 5mm; font-size: 9.2pt; page-break-inside: avoid; }
th { background: #e7f5f2; color: #0b566b; font-weight: 700; }
th, td { border: 0.35pt solid #9db8bd; padding: 2mm 2.2mm; vertical-align: top; }
blockquote { border-left: 3px solid #26a69a; margin: 4mm 0; padding: 1mm 4mm; color: #365b63; background: #f4fbfa; }
code { font-family: Consolas, monospace; background: #eef3f5; padding: 0.3mm 1mm; border-radius: 1mm; }
pre { background: #102a35; color: #e7faf6; padding: 4mm; border-radius: 2mm; white-space: pre-wrap; font-size: 8.5pt; page-break-inside: avoid; }
hr { border: 0; border-top: 0.5pt solid #b8cbcf; margin: 6mm 0; }
.cover { margin-top: 35mm; text-align: center; page-break-after: always; }
.cover h1 { border: 0; font-size: 28pt; margin-bottom: 10mm; }
.cover .subtitle { font-size: 15pt; color: #26a69a; margin-bottom: 24mm; }
.cover .meta { color: #506872; font-size: 11pt; }
.note { background: #fff8e6; border: 0.5pt solid #e0b34f; padding: 3mm 4mm; border-radius: 2mm; }
.footer { margin-top: 10mm; font-size: 8pt; color: #71868d; text-align: center; }
</style>
"""


def find_edge() -> Path:
    for candidate in EDGE_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("msedge") or shutil.which("chrome")
    if found:
        return Path(found)
    raise FileNotFoundError("Microsoft Edge/Chrome executable not found")


def render_markdown(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    title = html.escape(source.stem.replace("_", " "))
    return f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{body}<div class='footer'>GridRescue 碳韧智网 · Submission draft · 2026-08-26</div></body></html>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the GridRescue application Markdown as an anonymous A4 PDF")
    parser.add_argument("--source", type=Path, default=ROOT / "docs" / "submission_application_v10.md")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "submission_materials" / "GridRescue_赛道2_项目申报书.pdf")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    edge = find_edge()
    with tempfile.TemporaryDirectory(prefix="gridrescue_pdf_") as tmp:
        html_path = Path(tmp) / "submission.html"
        html_path.write_text(render_markdown(source), encoding="utf-8")
        cmd = [str(edge), "--headless", "--disable-gpu", "--no-sandbox", f"--print-to-pdf={output}", html_path.as_uri()]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if result.returncode != 0 or not output.exists():
            raise RuntimeError(f"Edge PDF render failed: rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}")
    print(f"output={output}")
    print(f"bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
