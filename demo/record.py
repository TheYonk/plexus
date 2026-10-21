"""Drive the Plexus UI through script.py and record it with Playwright.

Writes raw.webm and timeline.json under demo/out (or demo/out/<script>):
when each narration clip starts on the video clock, and which stretches
mux.py should speed up or cut.
The agent run is live, so a run can fail. A failed run is retried inside
the same take (steps 11 to 13 again, the failed attempt marked as a cut for
mux.py) up to --run-retries times before the "fail" narration is used.
The executive cut's veto works the same way: a wrong outcome is cut and
tried again. Generic markers: "@await:<js>" awaits a promise and speeds the
wait up; a step's "check" (JS returning a boolean) picks its ok / off
variant.

    api/.venv/bin/python demo/record.py [--script walkthrough|exec|deck] [--url http://127.0.0.1:8766/] [--headed]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import shutil
import sys
import time

from playwright.async_api import Page, async_playwright

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scripts import MODULES, load  # noqa: E402

W, H = 1920, 1080
PAD = 0.35  # silence after each clip
WAIT_TARGET_S = 6.0  # an agent run of any length plays back in about this long

HINT_JS = """() => {
  const li = [...document.querySelectorAll('#traj li')].find(l => l.querySelector('.hint'));
  if (!li) return false;
  li.scrollIntoView({block: 'center'});
  return plexusDemo.spotlight(li, 'tool error, matching hint, fixed on the next turn');
}"""


async def act(page: Page, action: str, rec: dict) -> None:
    if action.startswith("@pause:"):
        await asyncio.sleep(float(action.split(":", 1)[1]))
    elif action in ("@wait_run", "@wait_feed"):
        t_a = time.monotonic() - rec["t0"]
        while True:
            r = await page.evaluate("fetch('/ui/run').then(r => r.json())")
            if r["status"] != "running" or (action == "@wait_feed" and r.get("feed")):
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(1.2)  # let the page re-render
        t_b = time.monotonic() - rec["t0"]
        span = t_b - t_a
        if span > WAIT_TARGET_S + 2:
            rec["speed"].append({"start": round(t_a + 0.8, 3), "end": round(t_b - 1.2, 3), "factor": round((span - 2.0) / (WAIT_TARGET_S - 2.0), 3)})
        if action == "@wait_run":
            rec["run"] = r
        print(f"  {action} done after {span:.0f}s: {r['status']} {r.get('error', '')}", flush=True)
    elif action == "@veto":
        for attempt in range(rec["retries"] + 1):
            t_a = time.monotonic() - rec["t0"]
            r = await page.evaluate("execDemo.runVeto()")
            await asyncio.sleep(1.2)
            t_b = time.monotonic() - rec["t0"]
            cases = r.get("cases") or []
            ok = len(cases) == 2 and not cases[0]["landed"] and cases[1]["landed"]
            print(f"  @veto attempt {attempt + 1}: {t_b - t_a:.0f}s, {'ok' if ok else 'wrong: ' + json.dumps(cases)[:300]}", flush=True)
            if ok or attempt == rec["retries"]:
                break
            rec["cuts"].append({"start": round(t_a, 3), "end": round(t_b, 3)})
        rec["veto_ok"] = ok
        span = t_b - t_a
        if span > WAIT_TARGET_S + 2:
            rec["speed"].append({"start": round(t_a + 0.8, 3), "end": round(t_b - 1.2, 3), "factor": round((span - 2.0) / (WAIT_TARGET_S - 2.0), 3)})
    elif action.startswith("@await:"):
        t_a = time.monotonic() - rec["t0"]
        await page.evaluate(action.split(":", 1)[1])
        await asyncio.sleep(1.2)  # let the page re-render
        t_b = time.monotonic() - rec["t0"]
        span = t_b - t_a
        if span > WAIT_TARGET_S + 2:
            rec["speed"].append({"start": round(t_a + 0.8, 3), "end": round(t_b - 1.2, 3), "factor": round((span - 2.0) / (WAIT_TARGET_S - 2.0), 3)})
        print(f"  {action[:60]} done after {span:.0f}s", flush=True)
    elif action == "@spot_hint":
        rec["hint"] = await page.evaluate(HINT_JS)
        await asyncio.sleep(0.6)
    else:
        await page.evaluate(action)


def pick_clip(step: dict, rec: dict) -> str:
    if "say" in step:
        return step["id"]
    if "check" in step:
        return f"{step['id']}.{'ok' if rec['checks'][step['id']] else 'off'}"
    if step["id"].startswith("14-"):
        return f"{step['id']}.{'pass' if rec.get('passed') else 'fail'}"
    if step["id"].startswith("16-"):
        return f"{step['id']}.{'hint' if rec.get('hint') else 'clean'}"
    if step["id"].startswith("e04-"):
        return f"{step['id']}.{'ok' if rec.get('veto_ok') else 'off'}"
    raise KeyError(step["id"])


async def record_once(mod, out: pathlib.Path, url: str, headed: bool, run_retries: int) -> dict:
    STEPS = mod.STEPS
    durations = json.loads((out / "audio" / "durations.json").read_text())
    vid_dir = out / "video-tmp"
    shutil.rmtree(vid_dir, ignore_errors=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        ctx = await browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(vid_dir), record_video_size={"width": W, "height": H})
        page = await ctx.new_page()
        rec: dict = {"t0": time.monotonic(), "clips": [], "speed": [], "cuts": [], "retries": run_retries}
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{url}{mod.PAGE}")
        await page.wait_for_function(mod.READY_JS, timeout=15000)
        for js in getattr(mod, "SETUP_JS", []):
            await page.evaluate(js)
        await asyncio.sleep(1.0)
        run_block = next((i for i, s in enumerate(STEPS) if s["id"].startswith("11-")), None)
        t_block = 0.0
        i = 0
        try:
            while i < len(STEPS):
                step = STEPS[i]
                i += 1
                if step["id"].startswith("11-"):
                    t_block = time.monotonic() - rec["t0"]
                for a in step.get("pre", []):
                    await act(page, a, rec)
                if step["id"].startswith("14-"):
                    st = await page.evaluate("fetch('/ui/state').then(r => r.json())")
                    rec["passed"] = st["passed"]
                    if not st["passed"] and run_retries > 0:
                        run_retries -= 1
                        now = time.monotonic() - rec["t0"]
                        print(f"  run failed; cutting {t_block:.1f}s to {now:.1f}s and running again", flush=True)
                        rec["cuts"].append({"start": round(t_block, 3), "end": round(now, 3)})
                        rec["clips"] = [c for c in rec["clips"] if c["t"] < t_block]
                        rec["speed"] = [s for s in rec["speed"] if s["start"] < t_block]
                        await page.evaluate("plexusDemo.clearSpot()")
                        i = run_block
                        continue
                if "check" in step:
                    rec.setdefault("checks", {})[step["id"]] = bool(await page.evaluate(step["check"]))
                cid = pick_clip(step, rec)
                dur = durations[cid]
                t = time.monotonic() - rec["t0"]
                rec["clips"].append({"id": cid, "t": round(t, 3), "dur": dur})
                print(f"  {t:7.1f}s  {cid} ({dur:.1f}s)", flush=True)
                tasks = []
                for frac, a in step.get("at", []):
                    async def later(frac=frac, a=a):
                        await asyncio.sleep(frac * dur)
                        await act(page, a, rec)
                    tasks.append(asyncio.create_task(later()))
                await asyncio.sleep(dur + PAD)
                await asyncio.gather(*tasks)
                for a in step.get("after", []):
                    await act(page, a, rec)
        finally:
            rec["end"] = round(time.monotonic() - rec["t0"], 3)
            video = page.video
            await ctx.close()
            await browser.close()
        raw = out / "raw.webm"
        shutil.move(await video.path(), raw)
        shutil.rmtree(vid_dir, ignore_errors=True)
        rec["video"] = str(raw)
        rec["page_errors"] = errors
        rec.pop("t0")
        rec.pop("retries")
        return rec


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766/")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--run-retries", type=int, default=3)
    ap.add_argument("--script", choices=sorted(MODULES), default="walkthrough")
    args = ap.parse_args()
    mod, OUT = load(args.script)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"recording {args.script}", flush=True)
    rec = await record_once(mod, OUT, args.url, args.headed, args.run_retries)
    (OUT / "timeline.json").write_text(json.dumps(rec, indent=1, default=str))
    print(f"wrote {OUT / 'raw.webm'} and timeline.json ({rec['end']:.0f}s, page errors: {len(rec['page_errors'])})")


if __name__ == "__main__":
    asyncio.run(main())
