"""The Plexus walkthrough as data: what is said, and what the page does.

Each step is one narration clip. `pre` runs before the clip starts,
`at` entries fire at a fraction of the clip's length, `after` runs once the
clip has finished. Every action is a JS expression against
`window.plexusDemo` (see web/app.js), or a Python marker string that
record.py handles itself:

  "@wait_run"          block until the agent run finishes (sped up in mux)
  "@wait_feed"         block until the agent's first policy call (sped up)
  "@pause:<seconds>"   hold the frame

Steps with `variants` pick their text at record time (record.py decides
from what is on screen); voice.py renders every variant.
"""

VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # ElevenLabs premade voice "George"; PLEXUS_VOICE_ID overrides
MODEL_ID = "eleven_v4"  # audio tags ([excited], [laughs]) shape delivery; they are not spoken
PAGE = "?demo=1#stack"
READY_JS = "() => document.querySelector('#shell-state').textContent === 'connected'"
SETUP_JS = ["plexusDemo.sendToShell('clear')"]

D = "plexusDemo"

STEPS = [
    {
        "id": "01-open",
        "pre": [f"{D}.goto('stack')", "@pause:1.2"],
        "say": (
            "[thoughtful] Here's what bugs me about most agent demos. The agent lives in one place, "
            "the data lives somewhere else, the memory is a third service, and whatever is supposed "
            "to make the agent better lives in somebody's notebook. [excited] This is Plexus. One Postgres. "
            "The agent, its retrieval, its memory, and the loop that tunes it, all in the same database."
        ),
    },
    {
        "id": "02-synapse",
        "pre": [f"{D}.spotlight('#card-synapse', 'pg_synapse: the agent loop, inside the backend')"],
        "say": (
            "P G Sin-aps is the agent runtime, built as a Postgres extension. You call select, sin-aps "
            "dot execute, and the whole tool-calling loop runs inside the database."
        ),
    },
    {
        "id": "03-rag-stele-chunk",
        "pre": [f"{D}.spotlight('#card-rag', 'pg-raggraph: retrieval with effective dates')"],
        "at": [
            (0.36, f"{D}.spotlight('#card-stele', 'stele: memory that cites its evidence')"),
            (0.74, f"{D}.spotlight('#card-chunk', 'chunkshop: ingest')"),
        ],
        "say": (
            "P G Rag Graph does versioned retrieval. Documents carry effective dates, so you can ask "
            "what was true as of a given day. Steely is memory with receipts: every belief points at "
            "the evidence it came from, and a correction supersedes the old belief instead of erasing it. "
            "And chunkshop handles ingest, for the policy docs and for the agent's own past runs."
        ),
    },
    {
        "id": "04-llm",
        "pre": [f"{D}.spotlight('#card-llm', 'the only thing outside the database')"],
        "say": (
            "The only thing outside the database is the model. Right now that's Kwen three point six, "
            "a thirty-five billion parameter mixture of experts, running on a DGX Spark on my network."
        ),
    },
    {
        "id": "05-shell",
        "pre": [
            f"{D}.clearSpot()",
            f"{D}.spotlight('#dock', 'a real shell on this machine', 4)",
        ],
        "at": [
            (0.30, f"{D}.typeInShell(\"psql $DSN -Atc \\\"select 'pg_synapse ' || synapse.version(), model || ' @ ' || base_url from synapse.llm_profiles\\\"\", 40)"),
        ],
        "say": (
            "[casual] And this isn't a slide. That panel on the right is a real shell on this machine, wired "
            "into the app. Let me ask the database what it's running. P G Sin-aps zero point two, and "
            "the model is just a record in a table. Swapping models is an update, not a redeploy."
        ),
    },
    {
        "id": "06-policy",
        "pre": [f"{D}.clearSpot()", f"{D}.goto('policy')", "@pause:0.6", f"{D}.spotlight('#timeline', 'eight tickets, one policy change')"],
        "say": (
            "So here's the job. Eight support tickets, and four of them are refund requests. On July "
            "first the refund policy changed, and the window went from fourteen days to thirty. "
            "[curious] The catch? Each refund has to be decided under the policy that was in force on the day "
            "the ticket came in. Not the newest one. That trips up just about every RAG setup I've "
            "seen. [laughs] And a few humans too."
        ),
    },
    {
        "id": "07-compare",
        "pre": [f"{D}.clearSpot()", f"{D}.comparePolicy()", "@pause:1.5", f"{D}.spotlight('#compare', 'same question, two dates')"],
        "say": (
            "Same question, two dates. As of May twentieth, P G Rag Graph hands back version one. "
            "As of July twentieth, version two. [excited] Time travel, in sequel."
        ),
    },
    {
        "id": "08-harness2",
        "pre": [f"{D}.clearSpot()", f"{D}.goto('harness')", "@pause:0.8"],
        "say": (
            "[excited] Now the part I'm actually excited about. Google Research put out a project called "
            "harness two, and the idea is simple and kind of brilliant. Stop trying to make the model "
            "smarter. Hold the weights fixed, and optimize everything around it: the prompt, the rules, "
            "the tools, the hints. They call that the harness."
        ),
    },
    {
        "id": "09-harness-data",
        "pre": [f"{D}.spotlight('.meter', 'always-on context has a budget')"],
        "at": [(0.55, f"{D}.spotlight('#hc-system_prompt', 'always-on: paid on every turn')")],
        "say": (
            "We borrowed that. In P G Sin-aps, the harness is data. Every component is a record, and every "
            "component has a price, meaning how much context it costs and when. The system prompt, "
            "guardrails and memory are always on, so they're capped at twenty-four thousand characters, "
            "and the database enforces it."
        ),
    },
    {
        "id": "10-skills-hints-lessons",
        "pre": [f"{D}.openComponent('skills')", f"{D}.spotlight('#hc-skills', 'on demand: a trigger line until it is needed')"],
        "at": [
            (0.40, f"{D}.openComponent('hints')"),
            (0.40, f"{D}.spotlight('#hc-hints', 'in the loop: only when a tool fails')"),
            (0.70, f"{D}.openComponent('lessons')"),
            (0.70, f"{D}.spotlight('#hc-lessons', 'learned: written by the tuner')"),
        ],
        "say": (
            "Skills load on demand. The agent sees a one-line trigger until it actually needs the full "
            "playbook. Tool hints fire only when a tool call fails, right inside the loop. And lessons "
            "are written by the tuner itself. Hold that thought."
        ),
    },
    {
        "id": "11-run",
        "pre": [f"{D}.clearSpot()", f"{D}.goto('run')", "@pause:0.6", f"{D}.resetTickets()", "@pause:0.8"],
        "at": [(0.55, f"{D}.runAgent()")],
        "say": (
            "[excited] Let's run it. Reset the tickets so they're all blank, and kick it off. One sequel call."
        ),
    },
    {
        "id": "12-one-transaction",
        "pre": [f"{D}.spotlight('.tablewrap', 'nothing changes until the transaction commits')"],
        "say": (
            "While that runs, notice the table doesn't move. The whole run is one transaction, so "
            "nothing shows up until it commits. All or nothing. Which is exactly what you want when an "
            "agent is touching real data."
        ),
        "after": [f"{D}.clearSpot()", "@wait_feed"],
    },
    {
        "id": "13-policy-calls",
        "pre": [f"{D}.spotlight('#feed', 'live: the agent asking for the policy in force')"],
        "say": (
            "And there go the policy calls. For every refund, the agent asks the policy service what "
            "was in force on that ticket's date, and you can watch the answers land. Then it writes "
            "its decisions back with parameterized sequel, and logs one audit entry per ticket. "
            "[casual] I'll speed the rest of this up."
        ),
        "after": [f"{D}.clearSpot()", "@wait_run", "@pause:1.0"],
    },
    {
        "id": "14-result",
        "pre": [f"{D}.spotlight('#conds', 'the five checks the grader runs')"],
        "variants": {
            "pass": (
                "[excited] And there it is. Every ticket classified, the enterprise outage escalated, every "
                "refund decided under the right version of the policy, and one audit entry each. "
                "Five for five."
            ),
            "fail": (
                "[sighs] And this time it didn't get everything right. Which is honestly the point of the next "
                "part: the conditions tell you what failed, and the trajectory tells you why."
            ),
        },
    },
    {
        "id": "15-trajectory",
        "pre": [f"{D}.clearSpot()", f"{D}.goto('trajectory')", "@pause:1.0", f"{D}.spotlight('#traj', 'synapse.trajectory(execution_id)')"],
        "say": (
            "But the pass isn't the interesting part. The evidence is. Sin-aps dot trajectory renders "
            "the whole run, every action and every observation, straight out of the tables."
        ),
    },
    {
        "id": "16-hint",
        "pre": ["@spot_hint"],
        "variants": {
            "hint": (
                "[curious] And look at this one. A tool call failed, the matching hint got appended right to the "
                "error, and the agent fixed its own call on the very next turn. [laughs] Nobody wrote a retry "
                "handler for that."
            ),
            "clean": (
                "This run didn't hit a single tool error. Earlier runs did, and every one of those "
                "errors, with the hint that fixed it, is sitting in these tables as evidence."
            ),
        },
    },
    {
        "id": "17-tuner",
        "pre": [f"{D}.clearSpot()", f"{D}.goto('tuner')", "@pause:1.2"],
        "say": (
            "Which brings us to the tuner. This is the harness two loop, propose, probe, compose. "
            "It runs the base harness a couple of times, then hands those trajectories to an improver, "
            "Claude in this case. The improver proposes edits on two axes: how the agent works, and "
            "what a practitioner in the domain would know."
        ),
    },
    {
        "id": "18-tuner-chart",
        "pre": [f"{D}.spotlight('#chart', 'every rollout passed: selection went by cost')"],
        "say": (
            "Each proposal gets probed once, then the best ideas get composed into finals. Every one of "
            "these runs passed, so the tuner picked the cheapest. About thirty-seven percent fewer "
            "input tokens than the base."
        ),
    },
    {
        "id": "19-tuner-diff",
        "pre": [f"{D}.spotlight('#diff', 'the edit, as a diff')"],
        "say": (
            "And the change is readable. Instead of describing the sequel rules in prose, the adopted "
            "harness hands the agent one copy-ready statement per table. That alone stopped the "
            "retries on the first write."
        ),
    },
    {
        "id": "20-tuner-lesson",
        "pre": [f"{D}.spotlight('#lesson', 'reflect: one transferable lesson')"],
        "say": (
            "Then it reflects, and writes down one lesson for future tuning runs, citing the run it "
            "came from. That's lesson two, and it lives in a Postgres table."
        ),
    },
    {
        "id": "21-honest",
        "pre": [f"{D}.clearSpot()"],
        "say": (
            "[serious] Now, the honest part. On a small four billion parameter model, this same scenario tops out "
            "at three out of five. The bigger model is what got us to a pass, and the tuner made it "
            "cheaper. Model choice still matters. The harness is how you get the most out of whatever "
            "model you pick."
        ),
    },
    {
        "id": "22-shell-lessons",
        "pre": [f"{D}.spotlight('#dock', 'it is all just Postgres', 4)"],
        "at": [(0.25, f"{D}.typeInShell(\"psql $DSN -c \\\"select lesson_id, left(lesson, 60) as lesson, confidence from synapse.lessons\\\"\", 40)")],
        "say": (
            "And since it's all just Postgres, the lessons are one query away. No vector store bolted on "
            "the side. [laughs] No yammel files on somebody's laptop."
        ),
    },
    {
        "id": "23-close",
        "pre": [f"{D}.clearSpot()", f"{D}.goto('stack')", "@pause:0.6"],
        "say": (
            "So that's Plexus. One database running the agent, the retrieval, the memory, and the loop "
            "that makes it better. Harness two's ideas, living where your data already lives. The code "
            "is in the P G Sin-aps repo, on the harness two borrowings branch. [excited] Go break it."
        ),
        "after": ["@pause:2.0"],
    },
]
