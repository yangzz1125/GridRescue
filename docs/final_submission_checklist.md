# GridRescue 最终提交清单

## 工程

- [x] Streamlit 首屏可离线启动
- [x] `/_stcore/health` 健康检查返回 `ok`
- [x] 36 场景批处理证据存在
- [x] strict-contract-9 失败点保留
- [x] CVaR 风险报告已生成
- [x] MRV 500 次因子敏感性报告已生成
- [x] 全量测试 `61 passed`

## 材料

- [x] 申报书
- [x] 180 秒视频脚本
- [x] 评委问答与主张字典
- [x] 十日执行单
- [x] 官方赛事事实核验页

## 冻结口径

```text
strict_eligible=0
same_service_pass=false
claim_status=controlled_service_budget_inventory_difference
```

## 发布包

```text
GridRescue_Wave11_P1_Submission.zip
testzip=None
```

## 现场操作

```text
python scripts/smoke_demo.py
streamlit run app.py --server.headless true --server.fileWatcherType none
```

现场只展示：暴雨/高温成功路径、台风 BLOCKED 路径、MRV 抽屉、CVaR 卡和敏感性区间。
