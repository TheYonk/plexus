"""Render every narration clip in script.py with ElevenLabs.

Clips are cached in demo/out/audio/<step>[.<variant>].mp3 next to a .json
holding the hash of (voice, model, text), so editing one line re-renders one
clip. Durations come from ffmpeg and land in demo/out/audio/durations.json.

    ELEVENLABS_API_KEY=... api/.venv/bin/python demo/voice.py
"""

from __future__ import annotations

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
from script import MODEL_ID, STEPS, VOICE_ID  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent / "out" / "audio"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def clips() -> list[tuple[str, str]]:
    out = []
    for s in STEPS:
        if "say" in s:
            out.append((s["id"], s["say"]))
        for name, text in s.get("variants", {}).items():
            out.append((f"{s['id']}.{name}", text))
    return out


def duration(path: pathlib.Path) -> float:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        raise RuntimeError(f"no duration for {path}: {err[-300:]}")
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)


def tts(text: str, dest: pathlib.Path) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    body = json.dumps(
        {
            "text": text,
            "model_id": MODEL_ID,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True},
        }
    ).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    durations = {}
    for cid, text in clips():
        mp3, meta = OUT / f"{cid}.mp3", OUT / f"{cid}.json"
        h = hashlib.sha256(f"{VOICE_ID}|{MODEL_ID}|{text}".encode()).hexdigest()
        cached = mp3.exists() and meta.exists() and json.loads(meta.read_text()).get("hash") == h
        if not cached:
            print(f"tts  {cid} ({len(text)} chars)", flush=True)
            tts(text, mp3)
            meta.write_text(json.dumps({"hash": h, "text": text}))
        durations[cid] = round(duration(mp3), 3)
        print(f"{'ok  ' if cached else '    '} {cid}: {durations[cid]:.1f}s")
    (OUT / "durations.json").write_text(json.dumps(durations, indent=1))
    print(f"total narration (one variant each): {sum(v for k, v in durations.items() if not k.endswith(('.fail', '.clean'))):.0f}s")


if __name__ == "__main__":
    main()
