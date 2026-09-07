# GridRescue Wave 9：MRV 只读 UI 最小补丁设计

**审计日期：2026-08-22。**  
**范围：** 只读检查 `app.py` 与当前 `gridrescue-mrv-1.0` bundle；本轮未修改生产代码、测试或现有 artifacts。

---

## 1. P0 审计发现

### P0-1：MRV 页没有读取 MRV bundle

`app.py` 当前第 238-250 行附近的“MRV报告”页只展示 `selected.report` 和内存中的 dispatch CSV。它没有读取：

- `run_manifest.json`
- `evidence/seal.json`
- `evidence/verification.json`
- `outputs/claim_gates.json`
- `inputs/factor_registry.csv`

因此页面上的“MRV”目前是报告下载入口，不是证据包状态页。

### P0-2：不能把页面内存结果与归档 bundle 默认视为同一次运行

当前 Streamlit 每次通过 `cached_pipeline(scenario_name)` 重算；现有 MRV bundle 是 CLI 生成的归档 run。即使场景名称相同，也可能存在代码、配置或因子差异。UI 必须写“匹配场景的归档证据包”，并至少校验：

```text
manifest.scenario.name == scenario_name
manifest.network.source_sha256 == result.model.source_sha256
manifest.run_id == seal.run_id == verification.run_id
```

未通过时不得显示绿色 verified 状态。

### P0-3：`sealed` 与 `verified` 是两个状态

当前 schema 中：

- seal 状态来自 `run_manifest.status == "sealed"`；
- `seal.json` 只保存 hash 和边界说明，本身没有 `status` 字段；
- verification 结果来自重新执行 `verify_mrv_bundle(bundle_dir)`，不是仅信任历史 `verification.json`。

UI 应分别显示 `SEALED/NOT SEALED` 与 `PASS/FAIL`。单独看到 seal 文件不等于验证通过，也不等于第三方核证。

### P0-4：factor data class 不能从策略 gate 代替

`claim_gates.json` 中的 `strategies.<slug>.data_class = E_synthetic_demo` 描述策略运行数据；用户要求的 factor data class 应读取 `inputs/factor_registry.csv.source_class`。当前三条因子均为 `E`，同时为 `engineering_prior`、`approval_status=conditional`。UI 建议主指标显示 `E`，脚注显示 `3/3 engineering_prior · conditional`。

### P0-5：same-service gate 与 claim status 必须同时展示

当前 bundle 的比较层语义是：

```text
same_service_pass = false
same_service_reduction_claim_allowed = false
controlled_tradeoff_pass = true
claim_status = controlled_service_budget_inventory_difference
```

因此页面必须显示“严格同服务：未通过”和“主张：受控服务预算下的清单差异”，不能只显示负的 `inventory_difference_kgCO2`。

### P0-6：当前 manifest 时间戳晚于本次审计日期

现有 `run_manifest.created_at` 晚于 2026-08-22。UI 若展示该字段，应明确标为“artifact manifest timestamp”，不可将其渲染成当前时间或本次审计时间；提交前应重新生成日期一致的正式 bundle。

---

## 2. 最小改动目标

只修改 `app.py`，不改变 pipeline、MRV schema 或 CLI：

1. 自动发现与当前场景、网络 hash 匹配的最新归档 bundle；
2. 每次加载时调用 `verify_mrv_bundle(..., write_result=False)` 做只读实时复核；
3. 在现有 `tab5` 顶部显示六项状态；
4. 展示 verification 错误和 MRV 边界说明；
5. 将完整 bundle 在内存中打成 ZIP 下载，不写新文件；
6. 无 bundle、schema 缺失、场景不匹配或验证失败时页面仍可运行。

不新增第九个 tab，不改主流程，不在 Streamlit 中生成新 MRV bundle。

---

## 3. 具体插入位置

行号基于本次审计的 `app.py`。

### 插入 A：标准库导入区，第 3 行后

新增：

```python
import io
import json
import os
import zipfile
from typing import Any
```

在现有 GridRescue imports 中增加：

```python
from gridrescue.mrv import STRATEGY_SLUGS, verify_mrv_bundle  # noqa: E402
```

### 插入 B：`cached_pareto` 后、`result = cached_pipeline(...)` 前

加入 bundle 发现、加载、字段汇总和 ZIP 函数。保持它们为无 UI 副作用的纯读取函数。

### 插入 C：`selected` 与 `metrics` 赋值后

新增：

```python
mrv_bundle_dir = resolve_mrv_bundle(
    ROOT / "artifacts",
    scenario_name,
    result.model.source_sha256,
    override=os.getenv("GRIDRESCUE_MRV_BUNDLE"),
)
mrv_state = load_mrv_ui_state(mrv_bundle_dir) if mrv_bundle_dir else None
```

环境变量只用于测试、演示固定 bundle 和部署显式配置；即使设置，也必须继续校验场景与网络 hash。

### 替换 D：现有 `with tab5:` 块，第 238-250 行附近

保留当前 Markdown 报告与两个原下载按钮，在它们之前插入 `render_mrv_evidence_panel(...)`。完整 bundle 下载放在证据状态区内。

```python
with tab5:
    render_mrv_evidence_panel(mrv_state, scenario_name, strategy)
    st.divider()
    st.markdown(selected.report)
    # 保留当前 caption 与两个 download_button
```

---

## 4. 建议函数签名

```python
def resolve_mrv_bundle(
    artifact_root: Path,
    scenario_name: str,
    network_sha256: str,
    *,
    override: str | None = None,
) -> Path | None:
    """Return the newest matching archived bundle, never a mismatched run."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object and reject arrays/scalars with a clear ValueError."""


def summarize_factor_data_class(registry: pd.DataFrame) -> dict[str, str | int]:
    """Summarize source_class, method and approval status without hiding mixtures."""


def load_mrv_ui_state(bundle_dir: Path) -> dict[str, Any]:
    """Load schema files, run live verification and return a render-safe state."""


def build_mrv_bundle_zip(bundle_dir: Path) -> bytes:
    """Create an in-memory ZIP with sorted relative paths and no filesystem writes."""


def render_mrv_evidence_panel(
    state: dict[str, Any] | None,
    scenario_name: str,
    strategy_name: str,
) -> None:
    """Render seal, verification, factors and claim gates in the existing MRV tab."""
```

### `resolve_mrv_bundle` 行为

候选路径：

```python
artifact_root.glob("**/mrv/run-*/run_manifest.json")
```

筛选条件：

```python
manifest["scenario"]["name"] == scenario_name
manifest["network"]["source_sha256"].upper() == network_sha256.upper()
```

排序使用 manifest 的 `created_at` 字符串和 bundle 路径作为确定性次键。override 不是绕过筛选的后门；不匹配时返回 `None` 或在 state 中形成明确错误。

### `load_mrv_ui_state` 必需文件

```text
run_manifest.json
evidence/seal.json
evidence/verification.json
outputs/claim_gates.json
inputs/factor_registry.csv
```

推荐返回结构：

```python
{
    "bundle_dir": bundle_dir,
    "run_id": str,
    "manifest": dict,
    "seal": dict,
    "stored_verification": dict,
    "live_verification": dict,
    "claim_gates": dict,
    "factor_registry": pd.DataFrame,
    "factor_summary": dict,
    "semantic_errors": list[str],
    "display_verified": bool,
}
```

`display_verified` 的最小判定：

```python
display_verified = bool(
    manifest.get("status") == "sealed"
    and live_verification.get("verified") is True
    and not live_verification.get("errors")
    and not semantic_errors
)
```

`semantic_errors` 至少检查：

```text
manifest/seal/stored verification/live verification 的 run_id 一致
manifest.gates 与 outputs/claim_gates.json 完全一致
factor_registry 非空且含 source_class/method/approval_status
```

实时 verification 异常必须被捕获到 state，不得让整个 Streamlit 脚本崩溃。

### `build_mrv_bundle_zip` 行为

```python
def build_mrv_bundle_zip(bundle_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir).as_posix())
    return buffer.getvalue()
```

ZIP 仅是分发容器。seal 仍验证解压后的原始相对路径与内容，不把 ZIP hash 显示为第三方认证。

---

## 5. 字段映射

| UI 元素 | Schema 来源 | 当前示例 | 显示规则 |
|---|---|---|---|
| Seal 状态 | `run_manifest.status` | `sealed` | `SEALED`；若缺失/其他值显示 `NOT SEALED` |
| Run ID | `run_manifest.run_id` | `run-...` | 完整显示或短显示加完整 caption |
| 已校验文件 | live `verify_mrv_bundle.checked_files` | `11` | 整数；验证异常时显示 `-` |
| Verification | live `verified/errors` | `true / []` | PASS 用 success；FAIL 用 error 并列出 errors |
| Factor data class | `factor_registry.source_class` | `E` | 单一类显示 `E`；混合类显示 `MIXED: A,E...` |
| Factor 边界 | `method`, `approval_status`, `uncertainty_pct` | engineering prior / conditional / 20% | 作为 caption 或 dataframe，不塞进主指标 |
| 选中策略资格 | `gates.strategies[STRATEGY_SLUGS[strategy_name]].inventory_eligible` | true | 显示 Eligible/Blocked |
| Same-service gate | `gates.comparison.same_service_pass` | false | 显示“未通过”；不得被 controlled_tradeoff_pass 覆盖 |
| Claim status | `gates.comparison.claim_status` | controlled... | 使用受控中文映射，不直接把长枚举塞进 metric |
| 普通服务预算 | `normal_service_budget_fraction` | 0.08 | 显示 8%，仅 controlled 模式展示 |
| 清单差异 | `inventory_difference_kgCO2` | 负值 | 写“候选-参考清单差”，same-service=false 时禁用“减排”用词 |
| 证据边界 | `gates.boundary_note`, `seal.meaning`, `verification.meaning` | synthetic/file-integrity | 三条合并进 expander，避免默认页面过密 |

### Claim status 中文映射

```python
CLAIM_LABELS = {
    "same_service_inventory_reduction": "严格同服务清单降低",
    "controlled_service_budget_inventory_difference": "受控服务预算下的清单差异",
    "inventory_only": "仅排放清单",
}
```

未知值显示 `UNKNOWN (<raw value>)`，不要默认归入更强等级。

---

## 6. MRV 页最小布局

采用六列或两行三列，不新增嵌套卡片：

```text
Seal 状态 | Verification | 已校验文件 | Factor class | Same-service | Claim status
SEALED    | PASS         | 11         | E            | 未通过       | 受控服务预算差异
```

紧接一行：

```text
run_id · scenario · selected strategy eligibility · normal budget 8%
```

状态语义：

- `display_verified=true`：`st.success("MRV bundle 实时复核通过")`；
- live verification 失败：`st.error("MRV bundle 复核失败")`，展开错误列表；
- 只有 sealed 未 verified：`st.warning(...)`；
- 找不到匹配 bundle：`st.info("当前场景没有匹配网络 hash 的归档 MRV bundle")`；
- 即使 bundle 无效，也保留 ZIP 下载，便于取证，但按钮文案改为“下载待复核 MRV 证据包”。

同服务未通过时，建议使用：

> 当前比较属于“受控服务预算下的排放清单差异”；严格同服务门未通过，不形成同服务减排主张。

---

## 7. AppTest 设计与断言

新增 `tests/test_app_mrv.py`。当前环境 Streamlit 为 1.51.0，`download_button` 在 `AppTest` 中会作为 `UnknownElement` 出现，可通过 `at.get("download_button")` 检查 label/url。

### 7.1 正常 bundle

```python
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = (
    ROOT
    / "artifacts/flood_v08/mrv/run-7e495c4e6e73c188"
)


def test_mrv_tab_shows_verified_bundle(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=120).run()

    assert not at.exception
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["Seal 状态"] == "SEALED"
    assert metrics["Verification"] == "PASS"
    assert metrics["已校验文件"] == "11"
    assert metrics["Factor data class"] == "E"
    assert metrics["Same-service gate"] == "未通过"
    assert metrics["Claim status"] == "受控服务预算下的清单差异"
    assert any("实时复核通过" in item.value for item in at.success)
```

### 7.2 主张语义不得升级

```python
def test_controlled_claim_is_not_rendered_as_same_service_reduction(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=120).run()

    page_text = "\n".join(item.value for item in at.markdown)
    assert "严格同服务门未通过" in page_text
    assert "受控服务预算" in page_text
    assert "同服务减排" not in page_text
```

最后一条断言需限定在 MRV 新增文案或使用唯一固定句，避免旧报告正文未来合法出现解释性术语时产生脆弱测试。更稳妥的做法是给状态文本固定 key/固定 markdown 内容后精确匹配。

### 7.3 bundle 下载入口

```python
def test_mrv_bundle_download_is_rendered(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=120).run()

    downloads = at.get("download_button")
    bundle_downloads = [
        item for item in downloads
        if item.proto.label == "下载MRV证据包ZIP"
    ]
    assert len(bundle_downloads) == 1
    assert bundle_downloads[0].proto.url
```

### 7.4 场景不匹配时不得复用 flood bundle

```python
def test_mismatched_scenario_does_not_show_verified(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=120).run()
    at.selectbox[0].select("台风").run(timeout=120)

    assert not at.exception
    assert any("没有匹配" in item.value for item in at.info)
    metrics = {item.label: item.value for item in at.metric}
    assert metrics.get("Verification") != "PASS"
```

### 7.5 篡改 bundle 显示 FAIL

测试将 bundle 复制到 `tmp_path`，只修改 `outputs/activity_energy_hourly.csv` 的一个 `energy_kwh`，然后把 override 指向该副本：

```python
def test_tampered_bundle_is_visible_as_failed(monkeypatch, tmp_path):
    tampered = copy_bundle_fixture(BUNDLE, tmp_path / "tampered")
    mutate_first_energy_value(tampered / "outputs/activity_energy_hourly.csv")
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(tampered))

    at = AppTest.from_file(ROOT / "app.py", default_timeout=120).run()

    assert not at.exception
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["Verification"] == "FAIL"
    assert any("复核失败" in item.value for item in at.error)
    assert any("hash mismatch" in item.value for item in at.markdown + at.caption)
```

### 7.6 Schema 缺字段应降级，不应崩溃

至少参数化删除以下字段：

```text
verification.checked_files
factor_registry.source_class
claim_gates.comparison.same_service_pass
claim_gates.comparison.claim_status
```

断言：

```python
assert not at.exception
assert metrics["Verification"] == "FAIL"
assert any("schema" in item.value.lower() for item in at.error)
```

---

## 8. 验收清单

### P0 功能

- [ ] 暴雨场景展示 `SEALED / PASS / 11 / E / 未通过 / 受控服务预算下的清单差异`。
- [ ] 页面明确区分归档 bundle 与当前内存推演。
- [ ] 每次加载执行只读 live verification，不只读取历史 `verification.json`。
- [ ] factor class 来自 `factor_registry.source_class`。
- [ ] same-service=false 时没有“同服务减排”主张。
- [ ] ZIP 包含 manifest、inputs、outputs、evidence 全部现有文件。
- [ ] 台风/高温没有匹配 bundle 时显示 info，不借用 flood 证据。
- [ ] 篡改、缺文件、schema 缺字段均显示 FAIL，App 不崩溃。

### P0 测试

- [ ] `pytest -q tests/test_app_mrv.py` 通过。
- [ ] `pytest -q` 全量回归通过。
- [ ] `AppTest` 无 exception。
- [ ] 下载按钮通过 `at.get("download_button")` 被发现并具有 URL。

---

## 9. 最小补丁结论

该补丁只增加约 80-120 行只读加载与渲染代码，不改变优化、潮流、CareTask、MRV 生成或 schema。最重要的行为约束是：

> UI 展示的是一个经过现场重新复核的归档证据包；`sealed`、`verified`、`same-service` 和 `claim status` 分别来自不同字段，任何一层失败都不会被更强的绿色标签覆盖。

正式提交前还应重新生成时间戳与 2026-08-22 口径一致的 bundle，并为台风、极端高温各生成一份匹配的 MRV 证据包。
