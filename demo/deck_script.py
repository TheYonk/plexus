"""The deck as a narrated walkthrough: web/deck.html, slide by slide.

Same step format as script.py. Markers used here (handled by record.py):

  "@await:<js>"  await a promise (the live refunds), speeding the wait up
  "check"        JS returning a boolean, evaluated before the clip; picks
                 the step's "ok" or "off" variant

Spoken respellings, as in the other scripts: pg_synapse "P G Sin-aps",
pg-raggraph "P G Rag Graph", stele "Steely", Qwen "Kwen", SQL "sequel".
"in effect", never "in force" (heard as "enforced").
"""

VOICE_ID = "0L2sOpIAWLpsxLGbOsnX"  # ElevenLabs professional voice "The Yonk"
MODEL_ID = "eleven_v4"
PAGE = "deck?demo=1#1"
READY_JS = "() => window.deckDemo && deckDemo.ready"
SETUP_JS = ["deckDemo.resetPolicy()"]

D = "deckDemo"
AFTER_OK = "(p => !!(p.results.after && !p.results.after.landed && p.results.jul && p.results.jul.landed))(deckDemo.policy())"

STEPS = [
    {
        "id": "d01-title",
        "pre": [f"{D}.goto(1)", "@pause:1.0"],
        "say": (
            "[warm] This is Plexus. It's an answer to a question I kept asking about AI agents: why does the "
            "agent live so far away from the data it's making decisions about? [short pause] Let me show you "
            "what happens when you close that gap."
        ),
    },
    {
        "id": "d02-sprawl",
        "pre": [f"{D}.goto(2)", "@pause:0.6"],
        "at": [(0.45, f"{D}.spotlight('#sprawl')"), (0.9, f"{D}.clearSpot()")],
        "say": (
            "Here's the usual shape. The agent loop runs in an app server. Retrieval is a vector store. "
            "Memory is another service, and whatever makes the agent better lives in somebody's notebook. "
            "[serious] Five systems, and every line between them is a place where a run can half finish, or "
            "where two of them disagree about what actually happened."
        ),
    },
    {
        "id": "d03-postgres",
        "pre": [f"{D}.goto(3)", "@pause:0.6", f"{D}.spotlight('#c-syn')"],
        "at": [
            (0.27, f"{D}.spotlight('#c-rag')"),
            (0.45, f"{D}.spotlight('#c-stele')"),
            (0.62, f"{D}.spotlight('#c-chunk')"),
            (0.76, f"{D}.spotlight('#llmbox')"),
        ],
        "say": (
            "Plexus puts all of it in one Postgres. P G Sin-aps is the agent runtime: one sequel call runs the "
            "whole tool loop, inside a transaction. P G Rag Graph is retrieval that knows dates, so you can ask "
            "what was true on a given day. Steely is memory where every belief points at its evidence. "
            "Chunkshop does the ingest. And the only thing outside the database is the model. Kwen, in this "
            "case, and swapping it is an update to one record."
        ),
    },
    {
        "id": "d04-harness2",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(4)", "@pause:0.6"],
        "at": [(0.30, f"{D}.spotlight('#harness-list')"), (0.58, f"{D}.spotlight('#loop')")],
        "say": (
            "The other half of the idea comes from Google Research's harness two. [thoughtful] Stop trying to "
            "make the model smarter. Hold the weights fixed, and improve everything around it: the prompt, the "
            "rules, the tools, the hints. They call that the harness. The loop is simple. Propose changes from "
            "real runs, probe each one, compose the winners, and write down what you learned."
        ),
    },
    {
        "id": "d05-data",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(5)", "@pause:0.8"],
        "at": [(0.35, f"{D}.spotlight('#cost')"), (0.72, f"{D}.spotlight('#meter')")],
        "say": (
            "In Plexus, that harness is just data. Every piece is a record, and every record has a price: when "
            "it costs context. The always-on parts are capped by the database itself. Skills cost one line "
            "until they're needed. Tool hints appear only when a call fails. This agent uses under a fifth of "
            "its budget."
        ),
    },
    {
        "id": "d06-live",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(6)", "@pause:0.8", f"{D}.spotlight('#tl')"],
        "at": [(0.55, f"{D}.spotlight('#st-before')")],
        "say": (
            "[excited] Okay, the live part. This is a refund policy over a year. Version one gave you fourteen "
            "days, version two, thirty. Ticket one oh nine came in on October tenth, twenty-five days after the "
            "charge. There's an agent sitting on the refunds table as a trigger, and it checks the policy in "
            "effect on the ticket's date before anything commits. Let's try the refund."
        ),
        "after": [f"{D}.clearSpot()", f"@await:{D}.tryRefund('before')", "@pause:0.4"],
    },
    {
        "id": "d07-before",
        "pre": [f"{D}.spotlight('#r-before')"],
        "check": "deckDemo.policy().results.before?.landed === true",
        "variants": {
            "ok": (
                "Committed. Twenty-five days, inside version two's thirty. Fine. [short pause] Now legal decides "
                "thirty days is too generous, and shortens it to twenty-one, starting October first. So they "
                "publish version three."
            ),
            "off": (
                "[serious] That one should have gone through, and it didn't, so you're seeing the honest version "
                "of a live demo. The rest still holds. Legal shortens the window to twenty-one days from October "
                "first, and publishes version three."
            ),
        },
        "after": [f"{D}.clearSpot()", f"@await:{D}.publish()", "@pause:0.6"],
    },
    {
        "id": "d08-published",
        "pre": [f"{D}.spotlight('#band-v3')"],
        "at": [(0.55, f"{D}.spotlight('#r-publish')")],
        "say": (
            "That's it. One document into P G Rag Graph, and it took about a tenth of a second. Nobody touched a "
            "prompt. Nothing got redeployed. [curious] So, same refund. Same ticket. Again."
        ),
        "after": [f"{D}.clearSpot()", f"@await:{D}.runAfter()", "@pause:0.4"],
    },
    {
        "id": "d09-after",
        "pre": [f"{D}.spotlight('#r-after')"],
        "check": AFTER_OK,
        "at": [(0.55, f"{D}.spotlight('#r-jul')")],
        "variants": {
            "ok": (
                "[impressed] Rejected, inside the transaction, and the reason names version three and the "
                "twenty-one day window. And here's the part I love. The July ticket still went through, under "
                "version two, because that's the rule that was in effect on its day. New rules apply forward. "
                "Old decisions don't get rewritten."
            ),
            "off": (
                "[serious] That didn't land the way it should have. Every attempt is on the record, nothing "
                "half-committed, and you can see exactly which policy the agent read. That's the point of "
                "doing the check inside the transaction."
            ),
        },
        "after": ["@pause:0.6"],
    },
    {
        "id": "d10-audit",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(7)", "@pause:0.8", f"{D}.spotlight('#ch-0')"],
        "at": [
            (0.22, f"{D}.spotlight('#ch-1')"),
            (0.42, f"{D}.spotlight('#ch-2')"),
            (0.60, f"{D}.spotlight('#ch-3')"),
            (0.74, f"{D}.spotlight('#chain')"),
        ],
        "say": (
            "And when someone asks why the agent did something, this is the answer. Ticket one oh four. The "
            "policy in effect that day. The exact step in the run where the agent looked it up. What it decided, "
            "and the audit line it wrote. One query, one database. Not a log search across five services."
        ),
    },
    {
        "id": "d11-tuning",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(8)", "@pause:0.8"],
        "at": [(0.25, f"{D}.spotlight('#bignums')"), (0.70, f"{D}.spotlight('#x-lesson')")],
        "say": (
            "Then it gets cheaper. The tuner ran that same loop against this agent's own history, tested "
            "every change in a throwaway copy of the database, and adopted the cheapest version that still "
            "passed everything. Thirty-seven percent fewer tokens per ticket, eight out of eight runs passing. "
            "And it wrote down why, so the next round starts smarter."
        ),
    },
    {
        "id": "d12-vs",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(9)", "@pause:0.8"],
        "at": [(0.45, f"{D}.spotlight('#vs2 th.me')"), (0.62, f"{D}.spotlight('#vs2')")],
        "say": (
            "So why not just use harness two with the stack you've got? [thoughtful] Because harness two is a "
            "method, and a good one, but it tunes offline and hands you files. Plexus runs the same loop where "
            "the work happens. The run is a transaction, the veto sits where the data gets written, and adopting "
            "a change is an update with the evidence attached."
        ),
    },
    {
        "id": "d13-limits",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(10)", "@pause:0.8", f"{D}.spotlight('.limits li:nth-child(1)')"],
        "at": [
            (0.30, f"{D}.spotlight('.limits li:nth-child(2)')"),
            (0.55, f"{D}.spotlight('.limits li:nth-child(3)')"),
            (0.78, f"{D}.spotlight('.limits li:nth-child(4)')"),
        ],
        "say": (
            "[casual] Now the honest part, because somebody's going to ask. The model still matters: a small "
            "four billion parameter model tops out at three of five on this task. The veto is a model call per "
            "insert, so five to ten seconds. Great for refunds, not for a hot path. Long runs sometimes quit "
            "early. And any dollar figure you see attached to this is an assumption until you measure it."
        ),
    },
    {
        "id": "d14-next",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(11)", "@pause:0.8"],
        "at": [(0.3, f"{D}.spotlight('#road')")],
        "say": (
            "Each of those has a fix on the list. A rules fast path in front of the veto. Version history for the "
            "harness, so every change can be rolled back. Replaying old tickets to measure the real error rate. "
            "And a human approval queue for the borderline calls. None of it needs a new system. It's tables and "
            "triggers."
        ),
    },
    {
        "id": "d15-close",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(12)", "@pause:0.8"],
        "say": (
            "[warm] So that's Plexus. One Postgres running the agent, the retrieval, the memory, and the loop "
            "that makes it better. A policy change applies to the very next refund, and every decision can "
            "explain itself. [excited] Go try to break it."
        ),
        "after": ["@pause:2.0", f"@await:{D}.resetPolicy()"],  # leave v2 in effect, as found
    },
]
