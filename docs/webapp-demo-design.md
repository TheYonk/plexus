# Plexus web app, recorded walkthrough, voice-over

Started 2026-10-20 01:55 EST. The user asked for: a web app that shows the
Plexus demo, a panel that can see and interact with a shell, a step-by-step
walkthrough recorded with Playwright that talks through the harness2 ideas,
and an ElevenLabs voice-over on the video. They opted out of questions
("use your best judgment"), so every choice below is mine unless marked.

## Intent

Plexus already works (5/5 on Qwen3.6 with the tuned harness), but it lives in
a Makefile and psql output. The app makes the same facts visible in one
screen, and the video tells the story to someone who was not here: one
Postgres runs the agent, the retrieval, the memory and the ingest, and the
agent's harness is data that a tuner improves from the agent's own
trajectories.

## Goals

1. One page that shows, live: the tickets and the five conditions, the
   policy time-travel, the harness as data, a run in progress, the
   trajectory, the tune results, and a working shell.
2. The shell is real (a PTY on this machine), and the app can drive it:
   buttons type commands into it so the viewer sees the same thing a
   developer would.
3. A reproducible recording: one command produces `demo/out/plexus-demo.mp4`
   with the narration aligned to what is on screen.
4. Narration in the user's own ElevenLabs voice ("The Yonk",
   `0L2sOpIAWLpsxLGbOsnX`), in the-yonk persona's voice, covering the
   harness2 ideas the branch borrowed.

## Non-goals

- No auth system, no multi-user, no deployment. Localhost demo tool.
- No live 30-minute tune in the video; the tune is shown from its recorded
  output (`tuned/20261019-125722`), which is the honest artifact.
- No build step or JS framework.

## Anti-goals

- A shell reachable from the network. The API binds 0.0.0.0 because the DB
  container calls it; the shell must not ride along.
- A video that overclaims: the 4B model's 3/5, the "every rollout passed so
  partial scoring was not exercised" caveat, and the model mattering are
  part of the story.

## Design

### Backend: `api/ui.py` (APIRouter, mounted by `app.py`)

- `GET /` and `/static/*`: `web/index.html`, `web/app.js`, `web/style.css`,
  `web/vendor/xterm*` (vendored, so recording does not depend on a CDN).
- `GET /ui/state`: tickets joined with tier, `conditions.sql` rows,
  `assert.sql` verdict, audit counts, LLM profile, extension versions.
- `GET /ui/harness`: `synapse.agent_harness('triage_agent')`, skills, hints,
  lessons.
- `POST /ui/reset`: runs `scenario/seed.sql` (tickets only, harness kept).
- `POST /ui/run`: starts `synapse.execute` in a worker thread; one at a time.
  `GET /ui/run`: status, elapsed, the outcome when done, and the live feed.
- Live feed: `synapse.execute` is one transaction, so ticket writes are
  invisible until it commits. What is visible live is the agent's calls to
  this API (policy lookups), so `/policy/search` appends each call to an
  in-memory feed the UI polls. Honest and genuinely live.
- `GET /ui/trajectory/{id}`: `synapse.trajectory()` text split into steps.
- `GET /ui/tune`: the newest `tuned/*` run: rollouts from `summary.json`,
  selection, base vs adopted `system_prompt.md` diff, lessons.
- `WS /ui/shell`: bash in a PTY, cwd `plexus/`. Guarded three ways: off
  unless `PLEXUS_SHELL=1`, client must be loopback, and a per-process
  random token that `GET /ui/shell-token` hands out only to loopback
  clients.

### Frontend: `web/` (vanilla JS)

Single page, dark, 1920x1080-friendly. Left: a step rail (Stack, Policy
time-travel, Harness, Run, Trajectory, Tuner, Shell). Main area: the
selected section. A docked terminal (xterm.js) on the right that every
section can send commands to ("run in shell" buttons). `?demo=1` exposes
`window.plexusDemo` with `goto(section)`, `spotlight(selector, caption)`,
`caption(text)`, `clear()` for the recorder.

### Recording pipeline: `demo/`

- `script.py`: the walkthrough as data: ordered steps, each with narration
  text and an async action function against the page.
- `voice.py`: ElevenLabs TTS per step (`eleven_multilingual_v2`), cached by
  hash of voice + text in `demo/out/audio/`; duration from ffmpeg.
- `record.py`: Playwright (Python, Chromium, 1920x1080, `record_video`).
  For each step: mark `t_start`, run the action, then hold until the step's
  narration has finished (plus a short pad). Writes `timeline.json`.
- `mux.py`: ffmpeg (`imageio-ffmpeg` static binary; no system ffmpeg on the
  box): place each clip at its `t_start` with `adelay`, `amix`, encode
  H.264 + AAC to `demo/out/plexus-demo.mp4`.
- `make demo-video` runs voice, record, mux.

### Storyboard (about 6 to 8 minutes)

1. Cold open: the app, the one-line claim.
2. The stack: four projects, one Postgres.
3. The problem: tickets straddle a 1 July policy change; time-travel search
   for May vs July returns v1 vs v2.
4. The shell: it is real; `synapse.version()`, the LLM profile.
5. Harness as data (harness2: cost-tiered components): prompt, guardrails,
   memory, skills on demand, tool hints, lessons.
6. Run: reset, run, live policy lookups, then 5/5.
7. Trajectory (harness2: trajectories are the evidence): error, HINT,
   recovery.
8. Tuner (harness2: Propose-Probe-Compose, reflect, lessons): rollouts,
   what changed, lesson 2, token cut. Honest caveats.
9. Shell again: query `synapse.lessons` live.
10. Close.

## Todo

- [x] W1 `api/ui.py` state, harness, reset, trajectory, tune endpoints
- [x] W2 run worker + live feed hook in `/policy/search`
- [x] W3 guarded PTY websocket shell
- [x] W4 vendor xterm.js; `web/index.html`, `style.css`, `app.js`
- [x] W5 demo hooks (`?demo=1`, spotlight, caption)
- [x] W6 smoke-test every endpoint and the page in a browser
- [x] W7 narration script (the-yonk voice), AI-tell review
- [x] W8 `voice.py` + generate audio
- [x] W9 `record.py` + `timeline.json`
- [x] W10 `mux.py` + final mp4; watch-through check (frames + durations)
- [x] W11 Makefile targets, README/RUN.md notes, secret check, commit

## Implementation notes

### App

- `api/ui.py` is an `APIRouter` with a loopback-only dependency on every
  route; `app.py` mounts it, the `/ui/shell` websocket and `/static`. A
  request from the LAN address gets 403; the DB container's calls to
  `/policy/search` are unaffected (that route is not on the router).
- `/policy/search` now goes through `search_policy()` and appends each call
  to an in-memory feed; `/ui/policy/compare` calls `search_policy()`
  directly so the comparison does not pollute the run feed.
- Runs: one worker thread, `SET statement_timeout = '900s'`, then
  `synapse.execute`. Only one run at a time; reset is refused mid-run.
- Shell: `pty.fork()` + `bash --noprofile --norc -i`, cwd `plexus/`, with
  `DSN` exported and `PAGER=cat` (psql's pager swallowed the first demo
  query). Guards: `PLEXUS_SHELL=1`, loopback client, localhost `Origin`
  (blocks a cross-site page from opening the socket), and a per-process
  token. UTF-8 is decoded incrementally so a split multibyte char cannot
  garble the terminal.
- `make ui` restarts the API with the shell on; `make api` keeps it off.
  The restart now waits for the old uvicorn to exit (a curl right after
  `make ui` was answered by the dying process).
- xterm.js 5.5.0 and addon-fit 0.10.0 are vendored under `web/vendor/`.

### Recording pipeline

- Narration is in `demo/script.py` as data; `voice.py` caches clips by
  hash, so a one-line edit re-renders one clip (about 310 s of narration,
  roughly 6,000 characters of the ElevenLabs quota per full render).
- `record.py` waits for each clip's real duration, so pacing follows the
  voice, not guesses. Live waits (`@wait_feed`, `@wait_run`) are logged as
  speed-up stretches and `mux.py` plays them at whatever factor brings
  them to about 6 s, remapping every later clip's start time.
- Variants: the result line (pass or fail) and the trajectory line (a
  hint fired or not) are chosen from what is on screen. A failing run is
  retried once before the "fail" variant is used.
- No system ffmpeg on the box: `imageio-ffmpeg`'s static binary has
  libx264 and AAC. Playwright 1.64 and its Chromium went into
  `api/.venv`.
- First take review (frames pulled at points inside each clip) found the
  "watch the calls land" line playing before the first call, and the
  previous run's outcome on screen during a new run. Fixed by reordering
  (`@wait_feed` before that line) and clearing the outcome on start.

### Choices

- Vanilla JS, no build: the page is one screen with polling; a framework
  would add a toolchain for nothing.
- The tune is shown from `tuned/20261019-125722` rather than run live (30
  minutes). `tuned/` is gitignored, so the tuner panel needs a local run.
- The narration avoids per-run numbers (tokens, seconds) since the run is
  live and varies; the tuner numbers come from the recorded tune.

### Live-run reliability

- The adopted harness passed 5/5 in `make run`, in the UI smoke test and
  in the first take, then failed twice in a row: the agent wrote a final
  report claiming 8 tickets triaged after writing only 6 (107 and 108
  never updated). The recorder now retries the run block inside the take
  and `mux.py` cuts the failed attempt, so a take costs one extra run, not
  a full re-record.

## Next steps and gaps

- Premature completion is the next tuning target: a `make tune` with k
  large enough to see it (it showed up in 2 of about 6 live runs). A
  deterministic guard would also do: a critique step, or a final
  `SELECT count(*) WHERE category IS NULL` the harness requires before the
  report.

- The tuner's apply adds an edited tool hint next to the old one with the
  same pattern instead of replacing it (two "but expression is of type"
  hints). Small fix in `tune.py`.
- Lessons have no `source_execution` (the tuner writes evidence text, not
  an execution id); the UI shows the evidence instead.
- Playwright's built-in video is VP8 at a modest bitrate; if text looks
  soft, switch to CDP screencast frames.
