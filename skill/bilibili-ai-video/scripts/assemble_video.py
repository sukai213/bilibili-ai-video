# -*- coding: utf-8 -*-
"""剪辑成片：分段编码 -> 拼接 -> BGM 混音 -> 响度标准化(loudnorm)。

用法:
  python assemble_video.py --segments segments.json --meta audio/meta.json \
      --slides slides --audio audio --out . --ffmpeg <ffmpeg.exe>
"""
import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
SR = 44100
PAD = 0.35


def synth_bgm(duration, out_path):
    n = int(duration * SR)
    t = np.arange(n) / SR
    stereo = np.zeros((n, 2), dtype=np.float32)
    chords = [([220.00, 261.63, 329.63], 8.0),
              ([174.61, 220.00, 261.63], 8.0),
              ([261.63, 329.63, 392.00], 8.0),
              ([196.00, 246.94, 293.66], 8.0)]
    total, ci = 0.0, 0
    while total < duration:
        freqs, clen = chords[ci % 4]
        seg_n = int(clen * SR)
        seg_t = np.arange(seg_n) / SR
        env = np.minimum(1, seg_t / 2.0) * np.minimum(1, (clen - seg_t) / 3.0)
        env = np.clip(env, 0, 1) ** 1.5
        lfo = 1 + 0.06 * np.sin(2 * np.pi * 0.07 * seg_t) * np.sin(2 * np.pi * 0.11 * seg_t)
        mix = np.zeros(seg_n, dtype=np.float64)
        for f in freqs:
            mix += 0.32 * np.sin(2 * np.pi * f * seg_t)
            mix += 0.12 * np.sin(2 * np.pi * f * 2.01 * seg_t)
            mix += 0.05 * np.sin(2 * np.pi * f * 3.02 * seg_t)
        mix *= env * lfo
        a = 0.06
        mix_f = np.empty_like(mix)
        prev = 0.0
        for i in range(seg_n):
            prev = prev + a * (mix[i] - prev)
            mix_f[i] = prev
        s, e = int(total * SR), min(int(total * SR) + seg_n, n)
        if s >= n:
            break
        stereo[s:e, 0] += mix_f[: e - s].astype(np.float32) * 0.5
        stereo[s:e, 1] += mix_f[: e - s].astype(np.float32) * 0.5
        total += clen
        ci += 1
    noise = np.random.default_rng(7).normal(0, 1, n).astype(np.float32)
    noise = np.convolve(noise, np.ones(64) / 64, mode="same") * 0.006
    stereo[:, 0] += noise
    stereo[:, 1] += noise
    fade = np.minimum(1, t / 2.0) * np.minimum(1, (duration - t) / 4.0)
    stereo *= fade[:, None]
    data = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data.tobytes())
    print(f"BGM saved: {duration:.1f}s -> {out_path}")


def run(ffmpeg, cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print("CMD FAIL:", " ".join(cmd)[:300])
        print(r.stderr.decode("utf-8", errors="replace")[-1500:])
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--meta", required=True, help="TTS 生成的 meta.json")
    ap.add_argument("--slides", required=True, help="幻灯片目录")
    ap.add_argument("--audio", required=True, help="配音目录")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件路径")
    ap.add_argument("--bgm-volume", type=float, default=0.10)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    segments = json.load(open(args.segments, encoding="utf-8"))
    meta = json.load(open(args.meta, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)
    seg_dir = os.path.join(args.out, "seg")
    os.makedirs(seg_dir, exist_ok=True)

    durations = [meta[str(s["id"])]["duration"] for s in segments]
    total = sum(durations) + PAD * len(segments)
    print(f"total narration: {total:.1f}s")

    bgm = os.path.join(args.out, "bgm.wav")
    if not os.path.exists(bgm):
        synth_bgm(total + 2.0, bgm)

    concat_list = os.path.join(seg_dir, "list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for s, d in zip(segments, durations):
            sid = s["id"]
            img = os.path.join(args.slides, f"slide_{sid:02d}.png")
            wav = os.path.join(args.audio, f"seg_{sid:02d}.wav")
            out = os.path.join(seg_dir, f"seg_{sid:02d}.mp4")
            if not os.path.exists(out):
                dur = d + PAD
                run(args.ffmpeg, [args.ffmpeg, "-y", "-loop", "1", "-framerate", str(args.fps),
                                  "-t", f"{dur:.3f}", "-i", img, "-i", wav,
                                  "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                                  "-pix_fmt", "yuv420p", "-r", str(args.fps),
                                  "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                                  "-shortest", out])
                print(f"seg {sid:02d} encoded ({dur:.1f}s)", flush=True)
            f.write(f"file '{out}'\n")

    joined = os.path.join(args.out, "joined.mp4")
    if not os.path.exists(joined):
        run(args.ffmpeg, [args.ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", joined])
        print("joined ok", flush=True)

    final = os.path.join(args.out, "final.mp4")
    total_d = total + 2.0
    fade_out_v = max(total_d - 1.4, 0.1)
    fade_out_a = max(total_d - 2.0, 0.1)
    run(args.ffmpeg, [args.ffmpeg, "-y", "-i", joined, "-i", bgm,
                      "-filter_complex",
                      f"[0:v]fade=t=in:st=0:d=0.8,fade=t=out:st={fade_out_v:.2f}:d=1.2[v];"
                      f"[0:a]afade=t=in:st=0:d=1.2,afade=t=out:st={fade_out_a:.2f}:d=2.0[nar];"
                      f"[1:a]volume={args.bgm_volume}[bg];"
                      f"[nar][bg]amix=inputs=2:duration=first:dropout_transition=0[a]",
                      "-map", "[v]", "-map", "[a]",
                      "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                      "-pix_fmt", "yuv420p", "-r", str(args.fps),
                      "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                      final])
    print("FINAL:", final, flush=True)

    # 响度标准化（B 站建议 -16 LUFS 左右）
    loud = os.path.join(args.out, "final_loud.mp4")
    run(args.ffmpeg, [args.ffmpeg, "-y", "-i", final,
                      "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                      "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                      "-movflags", "+faststart", loud])
    print("LOUD:", loud, flush=True)


if __name__ == "__main__":
    main()
