"""Render every narration clip in script.py with ElevenLabs.

Clips are cached in demo/out/audio/<step>[.<variant>].mp3 next to a .json
holding the hash of (voice, model, text, neighbours), so editing one line
re-renders that clip and the two beside it. Each request carries the
neighbouring lines as previous_text / next_text and a fixed seed, so the
clips sound like one take rather than 23 separate ones. Durations land in
demo/out/audio/durations.json, integrated loudness (LUFS) in loudness.json;
mux.py uses the latter to level every clip to the same loudness.

    ELEVENLABS_API_KEY=... api/.venv/bin/python demo/voice.py [--script walkthrough|exec|deck]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

import imageio_ffmpeg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from scripts import MODULES, load  # noqa: E402

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


SEED = 4242


def clips(STEPS: list[dict]) -> list[tuple[str, str, str, str]]:
    """(clip id, text, previous line, next line); variants use their step's neighbours."""
    main = [s["say"] if "say" in s else next(iter(s["variants"].values())) for s in STEPS]
    out = []
    for i, s in enumerate(STEPS):
        prev = main[i - 1] if i > 0 else ""
        nxt = main[i + 1] if i + 1 < len(STEPS) else ""
        if "say" in s:
            out.append((s["id"], s["say"], prev, nxt))
        for name, text in s.get("variants", {}).items():
            out.append((f"{s['id']}.{name}", text, prev, nxt))
    return out


def duration(path: pathlib.Path) -> float:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        raise RuntimeError(f"no duration for {path}: {err[-300:]}")
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)


def loudness(path: pathlib.Path) -> float:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(json.loads(err[err.rindex("{"):err.rindex("}") + 1])["input_i"])


def tts(voice_id: str, model_id: str, text: str, prev: str, nxt: str, dest: pathlib.Path) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    body = json.dumps(
        {
            "text": text,
            "model_id": model_id,
            "previous_text": prev or None,
            "next_text": nxt or None,
            "seed": SEED,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "use_speaker_boost": True},
        }
    ).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", choices=sorted(MODULES), default="walkthrough")
    args = ap.parse_args()
    mod, out_dir = load(args.script)
    VOICE_ID, MODEL_ID = mod.VOICE_ID, mod.MODEL_ID
    OUT = out_dir / "audio"
    OUT.mkdir(parents=True, exist_ok=True)
    durations, lufs = {}, {}
    for cid, text, prev, nxt in clips(mod.STEPS):
        mp3, meta = OUT / f"{cid}.mp3", OUT / f"{cid}.json"
        h = hashlib.sha256(f"{VOICE_ID}|{MODEL_ID}|{SEED}|{prev}|{text}|{nxt}".encode()).hexdigest()
        cached = mp3.exists() and meta.exists() and json.loads(meta.read_text()).get("hash") == h
        if not cached:
            print(f"tts  {cid} ({len(text)} chars)", flush=True)
            tts(VOICE_ID, MODEL_ID, text, prev, nxt, mp3)
            meta.write_text(json.dumps({"hash": h, "text": text}))
        durations[cid] = round(duration(mp3), 3)
        lufs[cid] = round(loudness(mp3), 2)
        print(f"{'ok  ' if cached else '    '} {cid}: {durations[cid]:.1f}s {lufs[cid]:.1f} LUFS")
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1))
    (OUT / "loudness.json").write_text(json.dumps(lufs, indent=1))
    print(f"total narration (one variant each): {sum(v for k, v in durations.items() if "." not in k or k.endswith(('.pass', '.hint', '.ok'))):.0f}s")


if __name__ == "__main__":
    main()
