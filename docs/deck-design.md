# Plexus deck: a presentable slide show with a live policy change

Started 2026-10-21 07:15 EST. The user asked "make a presentation? a pptx
style slide show in html and walk through it? what other tech can we add?
any fixes" and, after a proposal, "do it". The proposal was: one HTML deck
served by the API that is (1) presented live, (2) recorded as a narrated
walkthrough with the existing pipeline, (3) exported to .pptx; with a live
policy change as the centerpiece, plus two quick fixes (veto trigger lost
on seed, "in force" heard as "enforced"). Choices below are mine.

## Intent

The two videos are watched. A deck is presented: someone stands in front
of a room, clicks through, runs a live moment, and leaves a .pptx behind.
It should work as a talk on its own and still be live where it counts.

## Goals

1. `GET /deck`: a 16:9 deck (fixed 1920x1080 stage scaled to the window),
   arrow keys / space / click to move, `S` opens a presenter window
   (notes, next slide, timer) kept in sync over a BroadcastChannel,
   `F` toggles fullscreen.
2. About 12 slides: title, the problem (too many systems), one Postgres,
   harness2 in one slide, the harness as data, LIVE policy change, the
   auditor's chain, measured tuning, Plexus vs harness2 vs a typical
   stack, honest limits, roadmap, try it.
3. **Live policy change** (the new "wow"): legal tightens the refund
   window from 30 to 21 days effective 1 October. A refund on a ticket
   from 10 October (25 days after its charge) is accepted under v2;
   publish v3 (one document into pg-raggraph, superseding v2); the same
   refund is now rejected by the veto agent; a July ticket is still judged
   under v2. No prompt edit, no redeploy.
4. `make deck-video`: narrated walkthrough of the deck through the same
   voice / record / mux pipeline (`--script deck`).
5. `make deck-pptx`: one .pptx with each slide as a full-bleed image and
   the speaker notes in the notes pane.
6. Fixes: `seed.sql` re-attaches the veto trigger itself; the exec cut
   says "in effect" instead of "in force" and is re-rendered.

## Non-goals

- Editable native PowerPoint shapes. The .pptx is a faithful leave-behind,
  not a source to edit; the HTML is the source.
- Building the roadmap items. The roadmap slide names them as next steps.

## Anti-goals

- Leaving demo state behind. The live policy change must not leave v3 or
  ticket 109 in the database, or the triage benchmark (8 tickets, four
  refunds) and the tune numbers would change under it.
- Claiming anything not shown: the limits slide is honest (4B model tops
  out at 3/5, the veto is an LLM call per insert, runs sometimes quit
  early, the dollar calculator rests on assumptions).

## Design

### Live policy change

- `scenario/policy-next/refund-policy-v3.md`: v3, effective 2026-10-01,
  supersedes v2, "full refund within 21 days"; 22 to 60 days only with a
  documented outage. Kept outside `scenario/policy/` so `make ingest`
  still loads v1 and v2 only.
- `app.py`: `ingest_docs(docs)` factored out of `/policy/ingest` so a
  single document can be ingested and superseded.
- `ui.py`:
  - `POST /deck/policy/reset`: delete the v3 document from pg-raggraph,
    clear v2's `effective_to`, forget the last result.
  - `POST /deck/policy/publish`: ingest v3 and supersede v2 as of its
    effective date; returns the policy in force on 2026-10-10 and on
    2026-07-20 afterwards.
  - `POST /deck/policy/try` `{case}`: case `oct` (ticket 109, created on
    the fly: pro, charged 2026-09-15, ticket 2026-10-10) or `jul` (ticket
    103). Inserts a $39 / $29 refund through the veto trigger, then
    deletes the refund and ticket 109 again. Returns landed / error /
    seconds and the policy in force for that ticket's date.
  - `GET /deck/policy/state`: v3 published or not, and the last results
    (so a reload or the .pptx export shows the finished slide).

### Pipeline

- `demo/deck_script.py`, registered in `scripts.py` as `deck`.
- `record.py` gains two generic markers so the deck needs no special
  cases: `@await:<js>` awaits a promise and speeds the wait up like a run;
  a step's `check` (JS returning a boolean, evaluated before the clip)
  picks the `ok` / `off` variant.
- `demo/export_pptx.py`: Playwright screenshots each slide at 1920x1080
  (`?print=1` hides the cursor and controls), python-pptx builds the deck
  with notes. python-pptx is installed into `api/.venv`.

## Todo

- [x] D1 fix: `seed.sql` re-attaches `policy_gate` when the agent exists
- [x] D2 v3 policy doc, `ingest_docs` refactor, `/deck/policy/*` routes
- [x] D3 verify the policy change end to end with curl (accept, publish, reject, July still v2, reset leaves no trace)
- [x] D4 `web/deck.html`, `deck.css`, `deck.js`: stage scaling, nav, presenter window, slides, live slide
- [x] D5 browser smoke test of every slide (Playwright screenshots)
- [x] D6 `record.py` markers (`@await`, `check`), `deck_script.py` narration (respellings, tags), AI-tell review
- [x] D7 voice, record, mux the deck video; transcript and frame check
- [x] D8 `export_pptx.py`, `make deck-pptx`; open-check the .pptx
- [x] D9 exec cut: "in force" to "in effect", re-render, transcript check
- [x] D10 Makefile, README, design notes, secret scan, commit

## Implementation notes

- D1: `seed.sql` ends with a `DO` block that calls
  `attach_agent_trigger` when `policy_gate` exists (attaching is idempotent:
  it drops the trigger by name first). On a first seed the agent does not
  exist yet and `agents.sql` attaches it. `make veto` after a reset now
  vetoes again; `_ensure_veto_trigger` in `ui.py` stays as a belt.
- D2/D3: v3 lives in `scenario/policy-next/`; `app.ingest_docs()` is the
  shared ingest+supersede path. Undo is `delete_document('policy:refund-v3')`
  (its `document_versions` row cascades) plus `effective_to = NULL` on v2.
  Measured: refund before v3 committed (v2, 4 to 10 s), publish 0.1 s,
  same refund after rejected with "refund-v3, 25 days since charge exceeds
  the 21-day window", ticket 103 still committed under v2. After reset:
  8 tickets, 0 refunds, v2 open-ended. Ticket 109 exists only for the
  length of each insert.
- D4: one stage, scaled with `translate(-50%,-50%) scale(k)`. IBM Plex
  Sans/Mono from Google Fonts, falling back to the system stack offline.
  Only the live slide and the harness loop are numbered (they are
  sequences). The live slide's state is server-side
  (`/deck/policy/state`), and each change is also broadcast, so the
  presenter window, a reload and the export all agree. `?demo=1` hides the
  footer and reset link for recording; `?print=1` also stops motion.
- D5: Playwright screenshots of all 12 slides, then the live slide driven
  by clicks with the presenter window open: no page errors, presenter in
  step. Fixed on the way: the timeline shrank inside the flex column and
  the step cards slid under it; a `.tl-axis` class collided with
  `style.css`; the presenter stage was off-centre.
- D6: `record.py` gained `@await:<js>` (await + speed-up) and per-step
  `check` (picks the ok/off variant), so the deck needed no special-case
  code. Narration transcribed with faster-whisper; three lines reworded
  ("hints" heard as "hence", "harness two loop" as "harness to loop",
  "next write" as "right").
- D7: `demo/out/deck/plexus-deck.mp4`, 5:20, 15 clips, no cuts; both
  checks true, so the "ok" variants played (refund committed under v2,
  rejected under v3, July ticket committed under v2). The live wait is
  sped up. Frames checked on a contact sheet.
- D8: python-pptx in `api/.venv` (also added to `make venv`) in place of
  pptxgenjs, which is not installed here: the slides are images, so
  there are no native charts or layouts to get wrong. Each picture has the
  headline as alt text; notes come from the slide's `<aside class="notes">`.
  The pptx skill's `validate.py` passes; LibreOffice renders all 12.
- D9: exec cut re-rendered: 4:03, veto right on the first attempt; e03
  and e05 now say "in effect" and transcribe that way.
- D10: the recorder and the exporter both unpublish v3 when they finish,
  so neither leaves the database changed.

## Next steps and gaps

- The .pptx is pictures of slides: good as a leave-behind, not editable.
  Native PowerPoint slides would mean a second source to keep in step.
- The live slide's notes say "in force"; spoken narration says "in
  effect". Notes are read by a person, so they were left alone.
- The veto on ticket 109 is an LLM call. It was right in every run so
  far (5 of 5 including the recording), but the narration has an "off"
  variant and the deck shows the agent's reason either way.
- Ticket 109 is created and deleted around each insert. If the API dies
  mid-insert, `/ui/reset` (or `make seed`) removes it.
- IBM Plex loads from Google Fonts; offline it falls back to the system
  sans, which reflows a few lines but fits.
- The roadmap slide's items are not built. The next sensible one is the
  rules fast path in front of the veto (milliseconds for clear cases).
