"""Start a local-only demo and capture desktop/mobile evidence."""
from pathlib import Path
import json
import socket
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/competition2026/validation'
OUT.mkdir(parents=True,exist_ok=True)
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0))
    port=sock.getsockname()[1]
log=(OUT/'streamlit.log').open('w',encoding='utf-8')
process=subprocess.Popen([sys.executable,'-m','streamlit','run','app.py','--server.headless','true','--server.address','127.0.0.1','--server.port',str(port),'--server.fileWatcherType','none','--browser.gatherUsageStats','false'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
url=f'http://127.0.0.1:{port}'
(OUT/'server.json').write_text(json.dumps(dict(url=url,pid=process.pid)),encoding='utf-8')
for _ in range(60):
    try:
        with urllib.request.urlopen(url+'/_stcore/health',timeout=2) as response:
            if response.read().strip()==b'ok': break
    except OSError: time.sleep(.5)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.goto(url)
    page.get_by_text('评委决策工作台',exact=True).wait_for(timeout=180000)
    page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    report={'url':url,'desktop_rendered':True,'mobile_body_width':page.evaluate('document.body.scrollWidth'),'mobile_viewport':390}
    (OUT/'browser_check.json').write_text(json.dumps(report),encoding='utf-8')
    browser.close()
print(url)
