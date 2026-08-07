# -*- coding: utf-8 -*-
"""批量 TTS 配音：逐段 design 模式生成，保存 wav + 时长元数据，支持断点续跑。

用法:
  python gen_tts.py --segments segments.json --out audio \
      --model-dir "C:\\Users\\Administrator\\Desktop\\Qwen3-TTS-Q5" \
      --voice "35岁男性科技主播，声音沉稳、磁性、冷静，普通话标准，语速适中"
"""
import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
# 必须：引擎打印 emoji 需要 UTF-8 控制台，否则初始化抛异常
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"


def est_steps(text):
    return int(len(text) * 0.30 * 12) + 160


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True, help="segments.json 路径")
    ap.add_argument("--out", required=True, help="音频输出目录（自动创建）")
    ap.add_argument("--model-dir", required=True, help="Qwen3-TTS-Q5 根目录（含 model-design）")
    ap.add_argument("--sys-path", default="", help="额外加入 sys.path 的目录（可多个，分号分隔）")
    ap.add_argument("--voice", default="35岁男性科技主播，声音沉稳、磁性、冷静，普通话标准，语速适中，略带金属质感的未来感")
    ap.add_argument("--provider", default="DML", help="ONNX provider: DML / CPU")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sub-seed", type=int, default=45)
    args = ap.parse_args()

    for p in [args.sys_path, args.model_dir, os.path.dirname(os.path.abspath(__file__))]:
        for part in p.split(";"):
            if part:
                sys.path.insert(0, part)

    segments = json.load(open(args.segments, encoding="utf-8-sig"))
    os.makedirs(args.out, exist_ok=True)
    meta_path = os.path.join(args.out, "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8-sig"))

    from qwen3_tts_gguf.inference import TTSEngine, TTSConfig

    model = os.path.join(args.model_dir, "model-design")
    engine = TTSEngine(model_dir=model, onnx_provider=args.provider, llm_use_gpu=True)
    stream = engine.create_stream()
    try:
        for seg in segments:
            sid = seg["id"]
            key = str(sid)
            wav = os.path.join(args.out, f"seg_{sid:02d}.wav")
            if os.path.exists(wav) and key in meta:
                print(f"[{sid}] skip (exists, {meta[key]['duration']:.2f}s)", flush=True)
                continue
            cfg = TTSConfig(max_steps=est_steps(seg["narration"]), temperature=0.7,
                            sub_temperature=0.7, seed=args.seed, sub_seed=args.sub_seed,
                            streaming=True)
            t0 = time.time()
            r = stream.design(text=seg["narration"], instruct=args.voice, config=cfg)
            if r is None or r.duration <= 0:
                print(f"[{sid}] FAILED, retrying...", flush=True)
                r = stream.design(text=seg["narration"], instruct=args.voice, config=cfg)
                if r is None or r.duration <= 0:
                    print(f"[{sid}] FAILED again, skip", flush=True)
                    continue
            r.save(wav)
            dt = time.time() - t0
            meta[key] = {"scene": seg["scene"], "title": seg["title"],
                         "text": seg["narration"], "duration": round(float(r.duration), 3),
                         "gen_s": round(dt, 2)}
            json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[{sid}] OK {r.duration:.2f}s (gen {dt:.1f}s) | {seg['narration'][:30]}...", flush=True)
    finally:
        stream.join()
        engine.shutdown()
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
