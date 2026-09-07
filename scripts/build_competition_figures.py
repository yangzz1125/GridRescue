"""Build source-indexed competition figures from current evidence only."""
from pathlib import Path
import hashlib
import json
import matplotlib.pyplot as plt
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/competition2026'
OUT=ART/'figures'
OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
index=[]


def save(fig,name,sources):
    path=OUT/name
    fig.tight_layout()
    fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white')
    plt.close(fig)
    index.append({'figure':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sources':';'.join(str(p.relative_to(ROOT)).replace('\\','/') for p in sources),'source_sha256':';'.join(hashlib.sha256(p.read_bytes()).hexdigest() for p in sources)})

# Strategy results for synthetic base cases
frames=[]
for label,slug in [('暴雨','flood'),('台风','typhoon'),('高温','heat')]:
    path=ART/'baseline'/slug/'strategy_comparison.csv'
    frame=pd.read_csv(path);frame['场景']=label;frames.append(frame)
data=pd.concat(frames)
fig,axes=plt.subplots(1,2,figsize=(12,4.5))
for strategy,group in data.groupby('strategy'):
    axes[0].bar([f'{x}\n{strategy[:2]}' for x in group['场景']],group.eens_kwh,label=strategy)
    axes[1].bar([f'{x}\n{strategy[:2]}' for x in group['场景']],group.total_carbon_kg,label=strategy)
axes[0].set_ylabel('EENS / kWh');axes[1].set_ylabel('运行清单 / kgCO2');axes[0].set_title('服务损失');axes[1].set_title('碳清单（服务不等价时不可直接比较减排）')
axes[1].legend(fontsize=8);save(fig,'01_strategy_comparison.png',[ART/'baseline'/x/'strategy_comparison.csv' for x in ('flood','typhoon','heat')])

# paired evidence
path=ART/'batch36/experiment_runs.csv';batch=pd.read_csv(path)
pivot=batch.pivot(index='scenario_id',columns='strategy',values=['eens_kwh','total_carbon_kg'])
valid=batch.pivot(index='scenario_id',columns='strategy',values='recommendation_eligible').fillna(False).all(axis=1)
dx=pivot['eens_kwh']['碳韧协同恢复']-pivot['eens_kwh']['最小失供恢复'];dc=pivot['total_carbon_kg']['碳韧协同恢复']-pivot['total_carbon_kg']['最小失供恢复']
fig,ax=plt.subplots(figsize=(7,5));ax.scatter(dx[valid],dc[valid],c='#187f67',label=f'合格配对 n={valid.sum()}');ax.scatter(dx[~valid],dc[~valid],c='#c53b3b',marker='x',s=80,label=f'排除 n={(~valid).sum()}');ax.axhline(0,color='black',lw=.8);ax.axvline(0,color='black',lw=.8);ax.set_xlabel('候选-参考 EENS / kWh');ax.set_ylabel('候选-参考清单 / kgCO2');ax.set_title('36场景配对：碳清单下降伴随服务让步');ax.legend();save(fig,'02_paired_tradeoff.png',[path,ART/'batch36/paired_report.json'])

# risk
path=ART/'risk_report.json';risk=pd.DataFrame(json.loads(path.read_text(encoding='utf-8'))['summaries'])
fig,ax=plt.subplots(figsize=(8,4.5));x=range(len(risk));ax.bar([i-.2 for i in x],risk['mean'],width=.4,label='均值');ax.bar([i+.2 for i in x],risk['cvar95'],width=.4,label='CVaR95');ax.set_xticks(list(x),risk.strategy);ax.set_ylabel('EENS / kWh');ax.set_title('均值与尾部风险（失败分母单列）');ax.legend();save(fig,'03_tail_risk.png',[path])

# strict eligibility
sources=list(ART.glob('pareto/*/strict/pareto_points.csv'));rows=[]
for path in sources:
    f=pd.read_csv(path);rows.append({'场景':path.parents[1].name,'通过':int(f.frontier_eligible.sum()),'阻断':int((~f.frontier_eligible).sum())})
frame=pd.DataFrame(rows);fig,ax=plt.subplots(figsize=(7,4));ax.bar(frame['场景'],frame['通过'],label='通过',color='#16836b');ax.bar(frame['场景'],frame['阻断'],bottom=frame['通过'],label='阻断',color='#c94d4d');ax.set_ylabel('扫描点');ax.set_title('严格生命线合同扫描：失败点不隐藏');ax.legend();save(fig,'04_contract_gates.png',sources)

# public profiles
sources=list((ROOT/'data/public/raw').glob('*wind.json'))+list((ROOT/'data/public/raw').glob('*rain.json'))+list((ROOT/'data/public/raw').glob('*heat.json'))
fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True)
for path in sorted(sources):
    hourly=pd.DataFrame(json.loads(path.read_text(encoding='utf-8'))['hourly']);label=path.stem
    axes[0].plot(hourly.temperature_2m,label=label);axes[1].plot(hourly.precipitation,label=label);axes[2].plot(hourly.wind_speed_10m,label=label)
axes[0].set_ylabel('温度 °C');axes[1].set_ylabel('降水 mm');axes[2].set_ylabel('风速 m/s');axes[2].set_xlabel('当地小时');axes[0].legend(ncol=3,fontsize=8);axes[0].set_title('三个历史天气窗口（ERA5再分析）');save(fig,'05_public_weather.png',sorted(sources))

# public outcome gate
path=ART/'public_replay/summary.csv';frame=pd.read_csv(path);fig,ax=plt.subplots(figsize=(10,4.5));frame['label']=frame['case']+'\n'+frame['strategy'].str[:2];colors=frame['care_pass'].map({True:'#16836b',False:'#c94d4d'});ax.bar(frame.label,frame.eens_kwh,color=colors);ax.set_ylabel('EENS / kWh');ax.set_title('公开天气驱动回放：红色为生命线任务阻断');ax.tick_params(axis='x',labelrotation=25);save(fig,'06_public_replay_gates.png',[path])

pd.DataFrame(index).to_csv(OUT/'figure_source_index.csv',index=False,encoding='utf-8-sig')
print(pd.DataFrame(index)[['figure','sources']].to_string(index=False))
