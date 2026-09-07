from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = Path(r"C:\Users\ASUS\Documents\ffmpeg-6.0-essentials_build\bin\ffmpeg.exe")
VOICE = "zh-CN-YunxiNeural"
SEGMENTS = [
    (30, "极端天气下，配电网恢复不是单一指标优化。暴雨内涝、台风和极端高温会同时影响关键服务、潮流安全、恢复速度和运行碳排。GridRescue把这些冲突放进同一个可复核的决策工作台。"),
    (25, "这里是三十三节点配电网故障拓扑。系统显式记录故障支路、联络线、孤岛和恢复动作时间线，所有结果都可以回放，不靠现场临时求解。"),
    (30, "我们对比传统顺序恢复、最小失供恢复和碳韧协同恢复。比较的不是一张漂亮的碳图，而是在相同场景、相同输入和相同证据结构下，观察服务、物理和排放的变化。"),
    (30, "第二道门是物理可行性。系统执行径向 P 与 Q 潮流、节点电压、支路热限、资源容量和孤岛平衡校验。缺少成网型电源的孤岛会被明确标记为 NO GFM 和 BLOCKED。"),
    (35, "公平 Pareto 扫描固定修复顺序和联络线方案，只允许普通服务在公开预算内让步。这样可以区分真实的受控服务差异，避免把少供电误写成严格同服务减排。当前 same service pass 等于 false，正式主张是受控服务预算下的运行碳清单差异。"),
    (30, "三道资格门分别是 Care、Physics 和 MRV。Care 把医院、通信、冷链等生命线任务写成带功率、时窗、截止时间、连续时长、依赖和电压阈值的服务合同。"),
    (35, "MRV 证据链把逐时活动量、因子注册表、碳清单、对账、动作链、行级哈希和封存状态串起来。验证器重新计算文件哈希和碳方程，改动活动账、因子或动作链后都会定位差异并失败。SEALED 只代表文件完整性和内部复算，不代表现场实测或第三方核证。"),
    (30, "生命线任务页面展示任务完成率、一级任务、最低任务电压和最长连续达标时间。系统不把关键服务藏在一个加权目标函数里，而是把它作为必须满足的硬合同。"),
    (25, "评委决策工作台将推荐、三门状态、风险卡、失败反例和证据入口集中在首屏。Wave11 同时展示均值、P九十五、CVaR九十五、失败预算和五百次确定性拉丁超立方因子传播。"),
    (25, "GridRescue 当前定位为离线预案、演练和复盘工作台，不写回现场 SCADA。下一步接入真实馈线、天气和权威排放因子，沿同一数据结构重新计算。我们不让碳数字看起来更低，而是让它在服务、物理和证据条件下值得被相信。"),
]


async def generate_tts(text: str, path: Path) -> None:
    await edge_tts.Communicate(text, VOICE, rate="+0%", volume="+0%").save(str(path))


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an AI-narrated GridRescue demo preview; replace narration before final submission")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "submission_materials" / "GridRescue_demo_narrated_ai_preview.mp4")
    args = parser.parse_args()
    ffmpeg = FFMPEG if FFMPEG.exists() else Path(shutil.which("ffmpeg") or "")
    if not ffmpeg.exists():
        raise FileNotFoundError("ffmpeg not found")
    video = ROOT / "artifacts" / "submission_materials" / "GridRescue_demo_preview.mp4"
    if not video.exists():
        raise FileNotFoundError(video)
    output = args.output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gridrescue_tts_") as tmp:
        tmp_path = Path(tmp)
        wav_paths: list[Path] = []
        for idx, (duration, text) in enumerate(SEGMENTS):
            mp3 = tmp_path / f"seg_{idx:02d}.mp3"
            wav = tmp_path / f"seg_{idx:02d}.wav"
            asyncio.run(generate_tts(text, mp3))
            run([str(ffmpeg), "-y", "-i", str(mp3), "-af", f"apad,atrim=duration={duration}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(wav)])
            wav_paths.append(wav)
        combined = tmp_path / "narration.wav"
        with wave.open(str(wav_paths[0]), "rb") as first:
            params = first.getparams()
            frames = [first.readframes(first.getnframes())]
        with wave.open(str(combined), "wb") as out:
            out.setparams(params)
            for frames_data in frames:
                out.writeframes(frames_data)
            for path in wav_paths[1:]:
                with wave.open(str(path), "rb") as segment:
                    out.writeframes(segment.readframes(segment.getnframes()))
        run([str(ffmpeg), "-y", "-i", str(video), "-i", str(combined), "-map", "0:v:0", "-map", "1:a:0", "-t", "295", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output)])
    print(f"output={output}")
    print(f"bytes={output.stat().st_size}")
    print("note=AI narration preview; replace with human narration before final submission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
