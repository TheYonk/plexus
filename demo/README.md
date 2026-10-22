# demo: narrated videos and the .pptx export

This directory turns the Plexus web pages into narrated videos, and the
deck into a .pptx. Every video is recorded from the real app: the agent
runs, the veto and the policy change in the videos are live, not mocked.

| Cut | Page | Script | Make target | Output |
| --- | --- | --- | --- | --- |
| Engineer walkthrough | `/` | `script.py` | `make demo-video` | `out/plexus-demo.mp4` |
| Executive cut | `/exec` | `exec_script.py` | `make exec-video` | `out/exec/plexus-exec.mp4` |
| Presentation | `/deck` | `deck_script.py` | `make deck-video` | `out/deck/plexus-deck.mp4` |
| Presentation as .pptx | `/deck?print=1` | (none) | `make deck-pptx` | `out/deck/plexus-deck.pptx` |

`out/` is gitignored. The deck itself is described in
[`../docs/deck.md`](../docs/deck.md).

## Requirements

- The stack running with the UI routes: `make up`, `make ingest`,
  `make seed`, then `make ui` (API on 8766).
- The venv from `make venv` (Playwright, python-pptx, imageio-ffmpeg),
  plus Playwright's Chromium once: `api/.venv/bin/playwright install chromium`.
- For the videos, `ELEVENLABS_API_KEY` in the environment. Never put it in
  a file in this repo.
- The agent model reachable (vLLM on .133, or whichever profile is set),
  because the recordings make real agent and veto calls.

## How a video is made

Three steps, each its own script, all taking `--script walkthrough|exec|deck`
(`walkthrough` is the default):

```bash
api/.venv/bin/python demo/voice.py  --script deck   # 1. narration
api/.venv/bin/python demo/record.py --script deck --url http://127.0.0.1:8766/   # 2. screen
api/.venv/bin/python demo/mux.py    --script deck   # 3. put them together
```

1. **`voice.py`** renders every narration clip with ElevenLabs into
   `<out>/audio/<step>[.<variant>].mp3`. Each request carries the lines
   before and after it and a fixed seed, so the clips sound like one take.
   Clips are cached by a hash of voice, model, text and neighbours: edit one
   line and only that clip and the two beside it are rendered again. It
   also writes `durations.json` and `loudness.json` (LUFS per clip).
2. **`record.py`** opens the page in Chromium at 1920x1080, waits for
   `READY_JS`, runs `SETUP_JS`, then plays the steps: actions before the
   clip, actions at fractions of the clip's length, the clip's length of
   silence plus a short pad, actions after. It writes `raw.webm` and
   `timeline.json`: when each clip starts on the video clock, which
   stretches to speed up (waits for the model), and which to cut (a failed
   live attempt that was retried). `--headed` shows the browser.
3. **`mux.py`** plays the sped-up stretches faster, drops the cuts, places
   each clip at its recorded time mapped through those edits, levels every
   clip to -16 LUFS, fades the clip edges, limits peaks, and writes the mp4.
   `--offset <s>` shifts all audio if voice and picture drift.

Waits on the model play back in about 6 s whatever they took, so a 40 s
agent run does not stall the video.

## The script format

A script module (`script.py`, `exec_script.py`, `deck_script.py`) defines:

| Name | Meaning |
| --- | --- |
| `VOICE_ID`, `MODEL_ID` | the ElevenLabs voice and model (`eleven_v4`) |
| `PAGE` | path to open, relative to `--url` |
| `READY_JS` | JS function; recording starts when it returns true |
| `SETUP_JS` | JS run once before the first step (optional) |
| `STEPS` | the list of steps |

Each step is one narration clip:

```python
{
    "id": "d07-before",                      # clip file name; keep ids unique
    "pre": ["deckDemo.spotlight('#r-before')"],   # before the clip
    "at": [(0.55, "deckDemo.clearSpot()")],  # at 55% of the clip
    "say": "Committed. Twenty-five days ...", # or "variants" plus "check"
    "after": ["@await:deckDemo.publish()"],  # after the clip
}
```

An action is a JS expression evaluated in the page (each page exposes a
scripting object: `plexusDemo`, `execDemo`, `deckDemo`) or a marker that
`record.py` handles itself:

| Marker | Does |
| --- | --- |
| `@pause:<s>` | hold the frame |
| `@wait_run` | wait for the agent run on `/` to finish (sped up) |
| `@wait_feed` | wait for the run's first policy call (sped up) |
| `@veto` | run the executive cut's veto; a wrong outcome is cut and retried |
| `@spot_hint` | spotlight the trajectory step where a tool hint fired |
| `@await:<js>` | await a promise, such as a live refund (sped up) |

**Variants.** A step can have `"variants": {"ok": ..., "off": ...}` in
place of `say`, so the narration matches what really happened on screen.
`voice.py` renders every variant; `record.py` picks one. The generic way to
choose is a `"check"`: a JS expression evaluated just before the clip, true
picks `ok`, false picks `off`. The older walkthrough steps (`14-`, `16-`,
`e04-`) are chosen by the run or veto result instead.

**Retries.** On the walkthrough, a failed agent run is retried inside the
same take up to `--run-retries` times (the failed attempt becomes a cut);
the "fail" narration is used only if every attempt fails.

## Writing narration

- Audio tags such as `[warm]`, `[serious]`, `[excited]` shape delivery and
  are not spoken. Use one at the start of a beat, not in every sentence.
- Spell names the way they should sound: "P G Sin-aps" (pg_synapse),
  "P G Rag Graph", "Steely" (stele), "Kwen" (Qwen), "sequel" (SQL).
  Write numbers as words ("twenty-one days", "one oh nine").
- Say "in effect", not "in force": the voice makes the latter sound like
  "enforced".
- After rendering, transcribe the clips and read them back. Lines that
  came back wrong so far: "hints" heard as "hence", "harness two loop" as
  "harness to loop", "next write" as "right". Reword rather than respell.
- Leave the database as you found it: the deck script ends with
  `resetPolicy()`.

## Adding a new cut

1. Write `demo/<name>_script.py` with the names above.
2. Register it in `scripts.py`: `MODULES["<name>"] = "<name>_script"`.
   Output goes to `out/<name>/`.
3. Add a Make target that runs voice, record and mux with `--script <name>`.
4. If the page needs a marker the table does not have, prefer `@await:`
   with a promise the page exposes over a new special case in `record.py`.

## The .pptx export

`export_pptx.py` opens `/deck?print=1` in Chromium, screenshots each slide
at 1920x1080 into `out/deck/slides/slide-NN.png`, and builds a 13.333 x 7.5
inch deck with python-pptx: one full-slide picture per slide, its headline
as alt text, its `<aside class="notes">` as speaker notes. If the live
slide has no results yet, it runs the policy change once first so the
picture shows a finished run. It always resets the policy to v2 at the end.

The slides are pictures, so text cannot be edited in PowerPoint. Edit
`web/deck.html` and export again.

## Files

| File | Role |
| --- | --- |
| `scripts.py` | registry: script name to module and output directory |
| `script.py`, `exec_script.py`, `deck_script.py` | what is said and what the page does |
| `voice.py` | ElevenLabs narration, cached per clip |
| `record.py` | Playwright recording and timeline |
| `mux.py` | speed-ups, cuts, levelling, final mp4 |
| `export_pptx.py` | deck screenshots to .pptx with notes |
