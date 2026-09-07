# GridRescue 最终提交清单

## 工程

- [x] Streamlit 首屏可离线启动
- [x] `/_stcore/health` 健康检查返回 `ok`
- [x] 36 场景批处理证据存在
- [x] strict-contract-9 失败点保留
- [x] CVaR 风险报告已生成
- [x] MRV 500 次因子敏感性报告已生成
- [x] 全量测试 `73 passed`

## 材料

- [x] 申报书
- [x] 五分钟视频脚本（目标4分55秒）
- [x] 评委问答与主张字典
- [x] 十日执行单
- [x] 官方赛事事实核验页

### 赛事日期硬检查（2026）

- [ ] HUST 校内截止日已向研究生院/培养单位确认（校内日可能早于全国日）
- [ ] 队长注册与队名/队员顺序在 **9 月 9 日**前完成（高校执行口径）
- [ ] 全员资格审核在 **9 月 11 日**前完成（赛事官网合并口径）
- [ ] 申报书、JPG 图、MP4 视频在 **9 月 13 日**前上传；视频 ≤5 分钟、≤200MB，PDF ≤40MB，JPG ≤40MB
- [ ] 参赛队伍 3–6 名真实学生；队名和全部材料已匿名化

官方来源：
- [赛事官网通知](https://cpipc.acge.org.cn/cw/contestNews/detail/2c90800c8093eef401809d348f8b0653/2c9080189ed9bdb5019ef242c9261327?page=0)
- [附件 1 赛题说明 PDF](https://cpipc.acge.org.cn/sysFile/downFile.do?fileId=927e029b55bc454887206137f78590f1)
- [东北农业大学校内执行通知（9/9、9/11、9/13 拆分）](https://graduate.neau.edu.cn/info/1164/4510.htm)

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

