"""Render the editable submission Markdown to printable HTML and PDF."""
from pathlib import Path
import markdown
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'docs/submission_application_2026.md'
html_path=source.with_suffix('.html')
pdf_path=ROOT/'release/submission_application_2026.pdf'
pdf_path.parent.mkdir(parents=True,exist_ok=True)
body=markdown.markdown(source.read_text(encoding='utf-8'),extensions=['tables','fenced_code'])
html=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>GridRescue 2026 申报正文</title><style>
@page {{ size:A4; margin:18mm 17mm; }} body {{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;line-height:1.65;color:#17212b;max-width:180mm;margin:auto;font-size:10.5pt}} h1{{font-size:21pt;text-align:center;margin:0 0 12mm}} h2{{font-size:15pt;border-bottom:1px solid #77858e;padding-bottom:2mm;break-after:avoid}} h3{{font-size:12pt;break-after:avoid}} p{{text-align:justify}} table{{border-collapse:collapse;width:100%;font-size:9pt}} th,td{{border:1px solid #9eabb2;padding:5px}} code{{background:#eef2f3;padding:1px 3px}} a{{color:#145e54;text-decoration:none}} ul,ol{{padding-left:1.5em}} </style></head><body>{body}</body></html>'''
html_path.write_text(html,encoding='utf-8',newline='\n')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto(html_path.as_uri(),wait_until='networkidle')
    page.pdf(path=str(pdf_path),format='A4',print_background=True,margin={'top':'0','bottom':'0','left':'0','right':'0'},display_header_footer=True,header_template='<span></span>',footer_template='<div style="font-size:8px;width:100%;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    browser.close()
print(html_path,pdf_path)
