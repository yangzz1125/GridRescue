"""Browser regression for the redesigned workbench against an existing local server."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:4158')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/frontend_review')
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, width, height in [('desktop', 1440, 1000), ('tablet', 1024, 1000),
                                     ('mobile', 390, 844), ('mobile_narrow', 320, 844)]:
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(args.url)
            page.get_by_role('tab', name='决策总览', exact=True).wait_for(timeout=180000)
            page.locator('.st-key-overview-map .scatterlayer .point').first.wait_for(timeout=180000)
            page.get_by_role('heading', name='医院生命线 CareTask', exact=True, include_hidden=True).wait_for(state='attached', timeout=180000)
            page.screenshot(path=str(output / f'{label}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), label
            assert page.locator('.kpi').count() == 6
            assert page.locator('.kpi-value').evaluate_all('''elements => elements.every(e => {
                const number = document.createRange();
                number.selectNodeContents(e.firstChild);
                return e.scrollWidth <= e.clientWidth + 1 && number.getClientRects().length === 1;
            })'''), (label, 'KPI number clipped or split')
            cards = page.locator('.strategy-results:visible .strategy-result')
            assert cards.count() == 3
            assert page.locator('.strategy-results:visible .strategy-result.selected').count() == 1
            assert cards.evaluate_all('''elements => elements.every(e =>
                e.scrollWidth <= e.clientWidth + 1)
            '''), (label, 'strategy card overflow')
            points = page.locator('.st-key-overview-map .scatterlayer .point').count()
            assert points == 33, points
            network = page.locator('.st-key-overview-map')
            assert network.locator('.imagelayer image').count() == 7
            images_loaded = network.locator('.imagelayer image').evaluate_all('''elements => Promise.all(elements.map(e =>
                new Promise(resolve => { const img = new Image(); img.onload = () => resolve(img.naturalWidth > 0);
                    img.onerror = () => resolve(false); img.src = e.href.baseVal; })
            ))''')
            assert all(images_loaded), (label, 'facility icon failed to load')
            canvas = network.locator('.st-key-network-canvas-overview-network')
            dimensions = canvas.evaluate('e => ({width:e.clientWidth, content:e.scrollWidth})')
            if label == 'desktop':
                assert dimensions['content'] <= dimensions['width'] + 1, dimensions
            else:
                canvas.evaluate('e => {e.scrollLeft = e.scrollWidth;}')
                assert canvas.evaluate('e => e.scrollLeft > 0'), (label, 'schematic cannot scroll')
                canvas.evaluate('e => {e.scrollLeft = 0;}')
            assert network.locator('.textpoint text').count() == 0
            network.get_by_text('全部节点编号', exact=True).click()
            expect(network.locator('.textpoint text')).to_have_count(26)
            labels = network.locator('.textpoint text')
            overlaps = labels.evaluate_all('''elements => {
                const boxes = elements.map(e => ({label: e.textContent, rect: e.getBoundingClientRect()}));
                return boxes.flatMap((a, i) => boxes.slice(i + 1).filter(b =>
                    a.rect.left < b.rect.right && a.rect.right > b.rect.left &&
                    a.rect.top < b.rect.bottom && a.rect.bottom > b.rect.top
                ).map(b => [a.label, b.label]));
            }''')
            assert not overlaps, (label, overlaps)
            point = network.locator('.scatterlayer .point').nth(3)
            point.evaluate("element => element.scrollIntoView({block: 'center', inline: 'center'})")
            box = point.bounding_box()
            page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            expect(network.locator('[data-testid="stMarkdownContainer"] strong')).to_have_text('N04 · 普通负荷', timeout=180000)
            network.get_by_text('全部节点编号', exact=True).click()
            expect(network.locator('.textpoint text')).to_have_count(0)
            expect(network.locator('[data-testid="stMarkdownContainer"] strong')).to_have_text('N04 · 普通负荷')
            network.get_by_role('button', name='展开电网图').click()
            dialog = page.get_by_role('dialog')
            expect(dialog).to_be_visible()
            expect(dialog.locator('.scatterlayer .point')).to_have_count(33)
            expect(dialog.locator('[data-testid="stMarkdownContainer"] strong')).to_have_text('N04 · 普通负荷', timeout=180000)
            dialog.screenshot(path=str(output / f'{label}_expanded.png'))
            page.keyboard.press('Escape')
            expect(dialog).not_to_be_visible()
            risk = page.get_by_test_id('stMetric').filter(has=page.get_by_text('风险优选策略', exact=True))
            expect(risk.get_by_test_id('stMetricValue')).to_have_text('最小失供恢复')
            clipped = risk.get_by_test_id('stMetricValue').evaluate('''element =>
                [element, ...element.querySelectorAll('*')].some(e =>
                    e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1)
            ''')
            assert not clipped, (label, 'risk strategy clipped')
            assert page.locator('[data-testid="stException"]').count() == 0
            checks.append({'viewport': label, 'width': width, 'network_points': points, 'overflow': False,
                           'node_label_overlaps': overlaps, 'risk_strategy_clipped': clipped,
                           'facility_icons': 7, 'node_click_details': True, 'number_toggle': True, 'expanded_view': True})
            risk.evaluate("element => {element.scrollIntoView({block: 'center'});}")
            page.screenshot(path=str(output / f'{label}_risk.png'), full_page=True)
            page.get_by_test_id('stMain').evaluate('element => {element.scrollTop = 0;}')
            if label == 'desktop':
                for tab in ['恢复数字孪生', '三策略对照', '能源与碳流', '潮流校验', 'MRV报告', '公平Pareto', '成岛护照', '生命线任务']:
                    page.get_by_role('tab', name=tab, exact=True).click()
                    assert page.get_by_role('tab', name=tab, exact=True).get_attribute('aria-selected') == 'true'
                    page.get_by_test_id('stMain').evaluate('element => {element.scrollTop = 0;}')
                    page.screenshot(path=str(output / f'tab_{tab}.png'), full_page=True)
                page.get_by_role('tab', name='决策总览', exact=True).click()
                slider = page.get_by_role('slider', name='恢复进程 / 小时')
                slider.focus()
                slider.press('ArrowRight')
                page.get_by_text('碳韧协同恢复 · T+05:00 · 33节点 / 5联络线', exact=True).wait_for(timeout=180000)
                page.screenshot(path=str(output / 'desktop_hour5.png'), full_page=True)
                checks.append({'all_tabs_navigable': True, 'hour_slider_updates': True})
            decision = page.locator('.st-key-overview-decision')
            qualification = decision.get_by_test_id('stMetric').filter(
                has=page.get_by_text('推荐资格', exact=True)
            ).get_by_test_id('stMetricValue')
            expect(qualification).to_have_text('PASS')
            decision.locator('summary').filter(has_text='证据预设').click()
            for preset, expected in [('NO_GFM反例 · BLOCKED', 'BLOCKED'),
                                     ('受控预算候选 · CLAIM GATED', 'CLAIM GATED'),
                                     ('主推荐 · PASS', 'PASS')]:
                decision.get_by_text(preset, exact=True).click()
                expect(qualification).to_have_text(expected, timeout=180000)
                assert page.locator('[data-testid="stException"]').count() == 0
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (label, preset)
                if expected == 'BLOCKED':
                    expect(decision.get_by_text('BLOCKED / NO_GFM 演示预设', exact=False)).to_be_visible()
                    decision.evaluate("element => element.scrollIntoView({block: 'start'})")
                    page.screenshot(path=str(output / f'{label}_blocked.png'), full_page=True)
                checks.append({'viewport': label, 'preset': preset, 'qualification': expected})
            page.close()
        browser.close()
    (output / 'checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == '__main__':
    main()
