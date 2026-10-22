# The Plexus deck

A 12-slide presentation served by the Plexus API at
http://127.0.0.1:8766/deck. It is plain HTML (`web/deck.html`,
`deck.css`, `deck.js`), so it is presented from a browser, recorded as a
narrated video, and exported to .pptx from the same source. Slides 5, 6, 7
and 8 read live data from the database; slide 6 changes it.

Why it was built this way, and what is still missing:
[`deck-design.md`](deck-design.md). The recording and export pipeline:
[`../demo/README.md`](../demo/README.md).

## Before you present

```bash
make up && make ingest && make seed   # once, if the stack is not running
make ui                               # API on 8766 with the UI routes
```

Then check:

1. The agent model answers. Slide 6 makes one LLM call per refund (the veto
   trigger). With vLLM on .133 that is 4 to 10 s; if the model is down the
   refund fails and the slide shows the error.
2. Slide 7 has a decision to show. It explains ticket 104, so a triage run
   must have happened since the last reseed. If the slide is empty, run
   one: `make run`, or the Run button on http://127.0.0.1:8766/.
3. The policy is back at v2. Open slide 6. If its timeline shows a v3
   band, click "Reset to v2".

The deck loads IBM Plex from Google Fonts. Offline it falls back to the
system sans, which reflows a few lines but still fits.

## Presenting

| Key or action | Does |
| --- | --- |
| Right arrow, Space, Page Down, click | next slide |
| Left arrow, Page Up | previous slide |
| Home / End | first / last slide |
| `S` | opens the presenter window: current slide, notes, next slide title, timer |
| `F` | toggles fullscreen |

The presenter window follows the main window, and the main window follows
it, over a `BroadcastChannel` named `plexus-deck`. Put the main window on
the projector and the presenter window on your laptop screen. The URL hash
is the slide number (`/deck#6`), so a reload stays on the same slide.

Clicks on buttons and links do not advance the slide, so the buttons on
slide 6 are safe to click.

URL options:

| Option | Effect |
| --- | --- |
| `?presenter=1` | the presenter layout (what `S` opens) |
| `?demo=1` | hides the footer and the reset link; used by the recorder |
| `?print=1` | hides the footer and stops motion; used by the .pptx export |

## The slides

| # | Title | Live? | What it shows |
| --- | --- | --- | --- |
| 1 | Plexus | | title |
| 2 | Five systems, one agent | | the usual agent stack: app server, vector store, memory service, notebook |
| 3 | One Postgres | | pg_synapse, pg-raggraph, stele, chunkshop in one database; the model is the only thing outside |
| 4 | The harness2 idea | | hold the weights, tune the harness; the propose, probe, compose, reflect loop |
| 5 | The harness is data | reads | each harness component and its context cost; the always-on budget meter (`/ui/harness`) |
| 6 | Live: the policy changes | writes | the live policy change, below |
| 7 | Explain any decision | reads | ticket 104: policy in effect, the step where the agent looked it up, the decision, the audit row (`/exec/audit/104`) |
| 8 | It got cheaper | reads | the tuner's measured saving: 26,431 to 16,645 tokens per ticket, 8/8 passing, and the lesson it wrote (`/exec/numbers`) |
| 9 | Why not harness2 alone | | Plexus, harness2 and a typical agent stack compared |
| 10 | The honest part | | the limits: model size matters, the veto is an LLM call, runs can quit early, dollar figures are assumptions |
| 11 | Next | | the roadmap: rules fast path, harness version history, replay measurement, approval queue |
| 12 | Try it | | where the code is |

Every slide has speaker notes in an `<aside class="notes">`, shown in the
presenter window and copied into the .pptx notes.

## The live policy change (slide 6)

The story: legal shortens the refund window from 30 days to 21, effective
1 October 2026. Nobody edits a prompt or redeploys anything.

The slide has three numbered steps and a timeline of the policy versions
(v1 14 days, v2 30 days, v3 21 days from 1 October once published).

1. **Try the refund.** Ticket 109 is dated 10 October; its charge was on
   15 September, 25 days earlier. A $39 refund is inserted into
   `support.refunds`. The `policy_gate` trigger agent asks pg-raggraph for
   the policy in effect on the ticket's date, gets v2 (30 days), and the
   insert commits.
2. **Publish v3.** `scenario/policy-next/refund-policy-v3.md` is ingested
   into pg-raggraph and supersedes v2 from 1 October. It takes about 0.1 s.
   The v3 band drops onto the timeline.
3. **Try it again.** The same refund is rejected inside the transaction:
   `synapse inline trigger rejected: refund-v3, 25 days since charge
   exceeds the 21-day window`. Then ticket 103 from July, 22 days after its
   charge, is tried and still commits, because v2 was in effect on its
   date.

**Reset to v2** (the link under the steps) deletes the v3 document, makes
v2 open-ended again and clears the results.

What it leaves behind: nothing. Ticket 109 is created just before each
insert and deleted with its refund straight after, and the July refund is
deleted too. The triage benchmark (8 tickets, 4 refund requests) is
unchanged whether you reset or not, but reset anyway, because a published
v3 changes what `/policy/search` returns for dates after 1 October.

If a refund comes out wrong (the veto is a model call), the slide shows
the agent's reason as it is. Say so and carry on; slide 10 is about
exactly this.

The routes behind the slide, all loopback-only like the rest of the UI:

| Route | Does |
| --- | --- |
| `GET /deck/policy/state` | `{v3, results, publish}`: is v3 published, and the last result of each step |
| `POST /deck/policy/publish` | ingest v3, supersede v2; returns the policy in effect on 2026-10-10 and 2026-07-20, and the seconds taken |
| `POST /deck/policy/try` `{"case": "oct" \| "jul", "label": ...}` | insert the refund through the trigger, then remove it; returns `landed`, `error`, `seconds`, `in_force` |
| `POST /deck/policy/reset` | delete v3, reopen v2, remove ticket 109 if present, clear results |

The same sequence from a terminal:

```bash
B=http://127.0.0.1:8766
curl -s -XPOST $B/deck/policy/reset
curl -s -XPOST $B/deck/policy/try -H 'content-type: application/json' -d '{"case":"oct","label":"before"}'
curl -s -XPOST $B/deck/policy/publish
curl -s -XPOST $B/deck/policy/try -H 'content-type: application/json' -d '{"case":"oct","label":"after"}'
curl -s -XPOST $B/deck/policy/try -H 'content-type: application/json' -d '{"case":"jul","label":"jul"}'
curl -s -XPOST $B/deck/policy/reset
```

Results are kept on the server, so a reload, the presenter window and the
.pptx export all show the same state of the slide.

## Video and .pptx

```bash
make deck-video   # -> demo/out/deck/plexus-deck.mp4 (about 5:20, narrated, slide 6 run for real)
make deck-pptx    # -> demo/out/deck/plexus-deck.pptx (12 slides, notes, alt text)
```

`deck-video` needs `ELEVENLABS_API_KEY` in the environment. Both need
`make ui` running, and both reset the policy to v2 when they finish.

The .pptx has one full-slide picture per slide. It is a leave-behind and
looks exactly like the HTML, but you cannot edit the text in PowerPoint.
Change the HTML and export again. If slide 6 has no results when you
export, the exporter runs the policy change once (about 20 s) so the
picture shows a finished run.

## Changing the deck

- **Slide content:** each slide is a `<section class="slide"
  data-title="...">` in `web/deck.html`, in order. `data-title` is what the
  presenter window shows as "Next" and what the .pptx names the picture;
  the first `h1`/`h2` becomes the .pptx alt text.
- **Notes:** the `<aside class="notes">` inside each section.
- **Adding or removing a slide:** the numbering comes from the order of the
  sections. Check `deck.js` for code that loads data on entering a slide
  by number (slides 5 to 8), and `demo/deck_script.py`, which moves with
  `deckDemo.goto(n)`.
- **Styles:** `web/deck.css`. It is loaded after `style.css`, so give new
  classes deck-specific names (a `.tl-axis` collision with `style.css` has
  bitten once already).
- **Narration:** `demo/deck_script.py`, one step per clip. See
  `demo/README.md` for the step format and the spoken respellings.
- **The live case:** the two refunds are in `DECK_CASES` in `api/ui.py`;
  the v3 text is in `scenario/policy-next/refund-policy-v3.md`.

`window.deckDemo` is the page's scripting surface for the recorder and the
exporter: `goto(n)`, `spotlight(selector)`, `clearSpot()`,
`tryRefund(label)`, `publish()`, `runAfter()`, `resetPolicy()`,
`loadHarness()`, `loadAudit()`, `loadNumbers()`, `policy()`, `ready`.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Slide 6 refund never comes back | the model endpoint is down or slow; check `curl http://192.168.1.133:8000/v1/models` |
| The first refund is rejected | v3 is still published from an earlier run; Reset to v2 and try again |
| Refunds commit even after v3 | check the publish result on the slide names v3 for 10 October; if it does, the model misjudged (the try route re-attaches the trigger before every insert, so a missing trigger is not the cause) |
| Slide 7 is empty | no triage run since the last seed; `make run` |
| Presenter window does not follow | it must be opened from the same origin (press `S` in the deck, do not paste a different host or port) |
| A stray ticket 109 | the API died mid-insert; `POST /deck/policy/reset`, `POST /ui/reset` or `make seed` removes it |
