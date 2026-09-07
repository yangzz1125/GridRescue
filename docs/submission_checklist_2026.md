# GridRescue 2026 提交检查单

## 自动完成项

- [x] 原环境和文件SHA基线已记录。
- [x] 旧基线测试61项通过。
- [x] 三灾种、36场景、严格合同和消融已重新执行。
- [x] 三段ERA5天气、官方年度因子网页和NOAA站点背景已冻结。
- [x] 三段公开天气已实际进入逐时负荷、光伏、调度、碳清单和MRV。
- [x] 公开回放三份MRV均独立复核通过。
- [x] 推荐显示同时要求Care、Physics、反馈和MRV资格。
- [x] 桌面与390px手机截图检查，无水平溢出。
- [x] 申报正文、技术报告、实验报告、来源说明、创新矩阵和演示素材完成。
- [x] 最终全量测试、匿名ZIP、解压启动复测（74项测试、9个合格MRV、ZIP逐文件SHA及两次健康启动均通过）。

## 人工必核

- [ ] 确认队伍3—6人、队长及全体队员参赛资格。
- [ ] 在9月11日前完成报名与资格审核，以官网最新通知为准。
- [ ] 在9月13日前提交作品，以官网最新通知为准。
- [ ] 将`submission_application_2026.pdf`内容套入官方申报书模板。
- [ ] 填写人员分工、指导教师、承诺和签字等真实字段。
- [ ] 检查材料、文件名、PDF属性、PPT和视频没有学校、学院、导师等盲审信息。
- [ ] 用户制作答辩PPT和5分钟内视频；使用`presentation_materials_2026.md`中的最新数字。
- [ ] 上传前在另一台电脑解压并启动一次。

## 统一主张

允许：真实公开天气再分析与官方统计因子驱动的公开算例仿真；三门资格；受控服务预算下的运行CO2清单差异；可复算证据包。

禁止：严格同服务减排；真实馈线、医院或停电工单；已接入SCADA/OMS；现场控制；灾害概率预测；第三方核证；全局最优。

## 运行

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH="$PWD\src"
python -m pytest -q
python scripts\check_submission_ready.py --run-tests --run-smoke
streamlit run app.py --server.address 127.0.0.1 --server.fileWatcherType none
```
