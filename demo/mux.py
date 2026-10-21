"""Lay the narration onto the recording: demo/out/plexus-demo.mp4.

Reads demo/out/timeline.json from record.py. Stretches listed under
"speed" (the wait for the live agent run) are played back faster; every
narration clip is placed at its recorded time mapped through those
speed-ups, so voice and screen stay in step. Every clip is gained to the
same loudness (from voice.py's loudness.json) and gets a short fade in and
out, so no clip jumps out and no clip edge clicks; a limiter guards peaks.

    api/.venv/bin/python demo/mux.py [--script walkthrough|exec|deck] [--offset 0.0]

--offset shifts all audio (seconds, + = later) if the video clock started
slightly before record.py's clock.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

import sys

import imageio_ffmpeg

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scripts import MODULES, load  # noqa: E402

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TARGET_LUFS = -16.0


def segments(end: float, speed: list[dict], cuts: list[dict] = ()) -> list[tuple[float, float, float]]:
    """(start, end, factor) over the recording; factor 0 means cut."""
    marks = [dict(s) for s in speed] + [{"start": c["start"], "end": c["end"], "factor": 0.0} for c in cuts]
    segs, t = [], 0.0
    for s in sorted(marks, key=lambda s: s["start"]):
        if s["start"] > t:
            segs.append((t, s["start"], 1.0))
        segs.append((s["start"], s["end"], s["factor"]))
        t = s["end"]
    if t < end:
        segs.append((t, end, 1.0))
    return segs


def mapper(segs):
    def f(t: float) -> float:
        out = 0.0
        for a, b, k in segs:
            if k == 0.0:
                if t < b:
                    return out
                continue
            if t >= b:
                out += (b - a) / k
            else:
                return out + max(0.0, t - a) / k
        return out

    return f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--script", choices=sorted(MODULES), default="walkthrough")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    OUT = load(args.script)[1]
    args.out = args.out or str(OUT / ("plexus-demo.mp4" if args.script == "walkthrough" else f"plexus-{args.script}.mp4"))
    tl = json.loads((OUT / "timeline.json").read_text())
    segs = segments(tl["end"], tl["speed"], tl.get("cuts", []))
    m = mapper(segs)
    total = m(tl["end"])

    inputs = ["-i", tl["video"]]
    fc = []
    kept = [(a, b, k) for a, b, k in segs if k != 0.0]
    for i, (a, b, k) in enumerate(kept):
        pts = "PTS-STARTPTS" if k == 1.0 else f"(PTS-STARTPTS)/{k}"
        fc.append(f"[0:v]trim=start={a}:end={b},setpts={pts}[v{i}]")
    fc.append("".join(f"[v{i}]" for i in range(len(kept))) + f"concat=n={len(kept)}:v=1:a=0,fps=30,format=yuv420p[v]")
    lufs = json.loads((OUT / "audio" / "loudness.json").read_text())
    for j, c in enumerate(tl["clips"], start=1):
        inputs += ["-i", str(OUT / "audio" / f"{c['id']}.mp3")]
        ms = max(0, int(round((m(c["t"]) + args.offset) * 1000)))
        gain = TARGET_LUFS - lufs[c["id"]]
        fade_out = max(0.0, c["dur"] - 0.08)
        fc.append(f"[{j}:a]aresample=44100,volume={gain:.2f}dB,afade=t=in:d=0.03,afade=t=out:st={fade_out:.3f}:d=0.08,adelay={ms}|{ms}[a{j}]")
    n = len(tl["clips"])
    fc.append("".join(f"[a{j}]" for j in range(1, n + 1)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,alimiter=limit=0.84:level=false,aresample=44100,apad[a]")

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
           "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", args.out]
    subprocess.run(cmd, check=True)
    print(f"wrote {args.out}: {total:.0f}s ({tl['end']:.0f}s recorded, {len(tl['speed'])} sped-up stretch(es), {len(tl.get('cuts', []))} cut(s), {n} clips)")


if __name__ == "__main__":
    main()
