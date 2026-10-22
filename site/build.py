"""Build the GitHub Pages site into site/_build.

  _build/index.html, site.css   the landing page (site/)
  _build/deck/                  web/deck.html with relative assets and the
                                recorded run (site/deck-snapshot.json) inlined,
                                so the deck works with no API
  _build/media/                 the three narrated videos, a poster frame each,
                                and the .pptx (from demo/out; make the videos first)

    api/.venv/bin/python site/build.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import imageio_ffmpeg

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = SITE / "_build"
OUTPUTS = ROOT / "demo" / "out"
MEDIA = {
    "plexus-deck.mp4": OUTPUTS / "deck" / "plexus-deck.mp4",
    "plexus-demo.mp4": OUTPUTS / "plexus-demo.mp4",
    "plexus-exec.mp4": OUTPUTS / "exec" / "plexus-exec.mp4",
    "plexus-deck.pptx": OUTPUTS / "deck" / "plexus-deck.pptx",
}
POSTER_AT = 4.0  # seconds in: past the fade, on the first slide or screen


def main() -> None:
    missing = [str(p.relative_to(ROOT)) for p in MEDIA.values() if not p.exists()]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)}: run make demo-video exec-video deck-video deck-pptx first")
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "deck").mkdir(parents=True)
    (OUT / "media").mkdir()

    for name in ("index.html", "site.css"):
        shutil.copy2(SITE / name, OUT / name)
    (OUT / ".nojekyll").write_text("")

    snap = json.loads((SITE / "deck-snapshot.json").read_text())
    html = (ROOT / "web" / "deck.html").read_text().replace('href="/static/', 'href="').replace('src="/static/', 'src="')
    tag = '<script src="deck.js"></script>'
    if tag not in html:
        raise SystemExit("web/deck.html no longer loads deck.js the way this build expects")
    inline = json.dumps(snap, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(tag, f"<script>window.DECK_SNAPSHOT = {inline};</script>\n{tag}")
    (OUT / "deck" / "index.html").write_text(html)
    for name in ("style.css", "deck.css", "deck.js"):
        shutil.copy2(ROOT / "web" / name, OUT / "deck" / name)
    (OUT / "deck" / "recorded.txt").write_text(snap["recorded"] + "\n")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for name, src in MEDIA.items():
        shutil.copy2(src, OUT / "media" / name)
        if name.endswith(".mp4"):
            poster = OUT / "media" / name.replace(".mp4", ".jpg")
            subprocess.run([ffmpeg, "-loglevel", "error", "-ss", str(POSTER_AT), "-i", str(src), "-frames:v", "1", "-q:v", "3", "-vf", "scale=1280:-2", str(poster)], check=True)

    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    biggest = max((p for p in OUT.rglob("*") if p.is_file()), key=lambda p: p.stat().st_size)
    print(f"wrote {OUT.relative_to(ROOT)}: {total / 1e6:.1f} MB, largest {biggest.name} {biggest.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
