# Plexus as open source: a fresh clone that runs, and a project site

Started 2026-10-22 00:15 EST. The user asked "Is plexus a project oss someone
can run?"; the answer was no, with a list of blockers. Then: "apache2, setup
git. There is a repo ready for it, don't publish until ready.
git@github.com:TheYonk/plexus.git", "Fix the other issues", and "Create a GH
pages website for it too, with our presentation and our video walk through".
Choices below are mine unless quoted.

## Intent

Someone who has never seen this machine clones `TheYonk/plexus`, follows
the README, and gets the same demo: the agent in Postgres, the as-of policy
lookups, the veto, memory, the deck. Someone who will never clone it can
watch the walkthrough and click through the presentation on a GitHub Pages
site.

## Goals

1. Apache-2.0 ("apache2"). The GitHub repo already has an Apache-2.0
   `LICENSE` as its only commit; local history is rebased on top of it.
2. No path, port or host from this machine in code: the chunkshop policy
   glob, the API URL the agent calls, the compose port.
3. `make deps`: clone pg-synapse, stele, pg-raggraph and chunkshop at
   pinned commits next to the checkout (or into `DEPS=`), from a `deps.lock`
   file. Pins are commits that exist on GitHub.
4. The narration voice is an env var with a stock ElevenLabs default; this
   machine keeps its own voice through the env.
5. A fresh clone works on its own: the tune numbers the UI, `/exec` and the
   deck show come from a committed reference run until `make tune` writes a
   new one.
6. README "Quick start" for a stranger, tested from a fresh clone on its own
   ports next to the running stack.
7. GitHub Pages site: a landing page with the three narrated videos, the
   presentation playable in the browser (its live slides replay a recorded
   real run, and say so), the .pptx to download, and how to run it.
8. Secret scan of the tree and the full history before the first push.
   Push only after the fresh-clone test passes ("don't publish until ready").

## Non-goals

- Packaging (pip, Docker Hub image). The database image is built locally.
- Merging pg-synapse's `harness2-borrowings` branch. The pin is a commit on
  that branch; the PR stays a separate decision.
- A hosted live demo. The site is static; live runs need the repo.

## Anti-goals

- Publishing a secret, a key, or anything that only works here.
- A site that pretends to be live. Replayed results are labelled as a
  recording, with the date.
- Bloating `main` with video. Videos live only on the `gh-pages` branch.

## Design

- **License:** `git fetch` + `git rebase origin/main` (the remote's only
  commit adds `LICENSE`). Add a short NOTICE line to the README.
- **Paths:** chunkshop expands `${VAR}` only in `dsn`, so `run_cell` runs
  chunkshop from the repo root and the cell uses the relative glob
  `scenario/policy/*.md`.
- **API URL:** `agents.sql` keeps `http://host.docker.internal:8766` as
  written; `make seed` substitutes `API_PORT` when it differs. The tuner
  copies the agent from the library database, so it follows.
- **Compose port:** the Makefile passes `PLEXUS_PG_PORT=$(PG_PORT)`; the
  build context is `${PLEXUS_SYNAPSE_DIR:-../pg-synapse}`.
- **Deps:** `deps.lock` lines `name url commit`; `make deps` clones each
  missing one into `$(DEPS)/<name>` and checks out the commit; an existing
  checkout is left alone with a warning if it is not at the pin. `make venv`
  and `make tune` use `$(DEPS)`.
- **Voice:** `PLEXUS_VOICE_ID` env, default a premade ElevenLabs voice.
- **Reference tune run:** `results/tune-reference/` holds the summary and
  the base/adopted harness files of the run the deck quotes (20261019-125722,
  Qwen3.6). `ui.tune()` reads `tuned/*` first and falls back to it.
- **Site:** `site/` holds the landing page source; `make site` builds
  `site/_build/` (gitignored): landing page, `deck/` (the deck with a static
  data layer), `media/` (mp4s, poster frames, pptx). `deck.js` gets a
  snapshot mode: when `window.DECK_SNAPSHOT` is set, `api()` answers from it
  and the live slide replays the recorded results with their real timings
  shortened. `demo/snapshot.py` captures the snapshot from the running API
  (harness, audit 104, numbers, one real run of the policy change).
  Published by pushing `_build` to an orphan `gh-pages` branch; Pages is
  enabled on that branch through `gh api`.

## Todo

- [ ] R1 rebase onto the remote's LICENSE commit; README license line
- [ ] R2 relative chunkshop glob (`run_cell` cwd = repo root)
- [ ] R3 `agents.sql` API port substitution in `make seed`; compose port and context from the Makefile
- [ ] R4 `deps.lock` + `make deps`; `DEPS` in `venv`, `tune`, compose
- [ ] R5 `PLEXUS_VOICE_ID` with a stock default
- [ ] R6 reference tune run committed; `tune()` fallback
- [ ] R7 deck "Try it" slide and README quick start for a fresh clone
- [ ] R8 fresh-clone test on other ports: deps, venv, up, ingest, seed, run, veto, memory, ui pages
- [ ] R9 deck snapshot mode, `demo/snapshot.py`, landing page, `make site`; browser check of the built site
- [ ] R10 secret scan (tree + history), push `main`, push `gh-pages`, enable Pages, check the live URL

## Implementation notes

(filled in as items land)

## Next steps and gaps

(filled in at the end)
