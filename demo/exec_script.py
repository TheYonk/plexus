"""The executive cut as data: a customer outcome, for the person who signs.

Same step format as script.py. Extra markers handled by record.py:

  "@veto"   run the two refund inserts against the policy_gate trigger;
            a wrong outcome is retried (the attempt is cut in mux) up to
            --run-retries times, the wait itself is sped up
"""

VOICE_ID = "0L2sOpIAWLpsxLGbOsnX"  # ElevenLabs professional voice "The Yonk"
MODEL_ID = "eleven_v4"
PAGE = "exec?demo=1#1"
READY_JS = "() => window.execDemo && document.querySelector('#n-base').textContent !== '…'"

D = "execDemo"

STEPS = [
    {
        "id": "e01-open",
        "pre": [f"{D}.goto(1)", "@pause:1.0"],
        "at": [(0.55, f"{D}.spotlight('#profile', 'an illustrative customer, at real scale')")],
        "say": (
            "[confident] Let's talk about a problem at real scale. A subscription retailer, two million "
            "support tickets a month. About four hundred thousand of those need a refund decision, and "
            "every one of them is either money walking out the door, or a customer walking out the door. "
            "They want an AI agent on that queue. Great. [short pause] Then the board asks three questions."
        ),
    },
    {
        "id": "e02-risks",
        "pre": [f"{D}.goto(2)", "@pause:0.6", f"{D}.spotlight('#risk-money')"],
        "at": [
            (0.30, f"{D}.spotlight('#risk-audit')"),
            (0.55, f"{D}.spotlight('#risk-cost')"),
            (0.80, f"{D}.clearSpot()"),
        ],
        "say": (
            "One. Can it give away money it shouldn't? Policies change every quarter, and an agent that "
            "reads today's policy for last month's ticket gets it wrong at machine speed. Two. Can we "
            "explain any single decision, to a customer, to a card network, to a regulator? Three. Does "
            "it get better over time, or just more expensive? [thoughtful] Most teams can't answer any of "
            "those with a straight face. So let's answer them. Live."
        ),
    },
    {
        "id": "e03-veto",
        "pre": [f"{D}.goto(3)", "@pause:0.8"],
        "at": [(0.45, f"{D}.spotlight('#veto', 'two refunds, one of them breaks the policy')")],
        "say": (
            "Question one. In Plexus, the agent doesn't sit next to the database. It sits inside it. "
            "There's an agent attached to the refunds table as a trigger. Before a refund can commit, it "
            "checks the policy that was in effect on the day the ticket came in. Let's try two refunds."
        ),
        "after": [f"{D}.clearSpot()", "@veto", "@pause:0.6"],
    },
    {
        "id": "e04-veto-result",
        "pre": [f"{D}.spotlight('#vcase-0', 'rejected inside the transaction')"],
        "at": [(0.62, f"{D}.spotlight('#vcase-1', 'committed')")],
        "variants": {
            "ok": (
                "[impressed] There it is. The sixty-one day refund? Rejected, inside the transaction, with "
                "the agent's reason as the database error. That row never existed. The twenty-two day one "
                "went straight through. No reconciliation job, no cleanup script, no 'we'll catch it in the "
                "monthly audit.'"
            ),
            "off": (
                "[serious] That one didn't go the way it should, and that's exactly why the check lives in "
                "the transaction, with every attempt on the record. Nothing half-landed, and you can see "
                "precisely why."
            ),
        },
    },
    {
        "id": "e05-audit",
        "pre": [f"{D}.clearSpot()", f"{D}.loadAudit(104)", f"{D}.goto(4)", "@pause:1.0", f"{D}.spotlight('#ch-0')"],
        "at": [
            (0.17, f"{D}.spotlight('#ch-1')"),
            (0.33, f"{D}.spotlight('#ch-2')"),
            (0.46, f"{D}.spotlight('#ch-3')"),
            (0.56, f"{D}.spotlight('#chain', 'one database, one query')"),
        ],
        "say": (
            "Question two. Explain a decision. Here's ticket one oh four. What the customer asked. The "
            "policy that was in effect on that exact day: version two, where past sixty days you get "
            "account credit, not cash. The exact step in the agent's run where it looked that up. What it "
            "decided, credit, and the audit line it wrote. "
            "All of it comes out of one database. [serious] When someone asks why the AI did that, this "
            "is the answer. Not a shrug and a pile of logs."
        ),
    },
    {
        "id": "e06-cheaper",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(5)", "@pause:0.8"],
        "at": [
            (0.50, f"{D}.spotlight('#nums', 'measured: same model, same checks passed')"),
            (0.82, f"{D}.spotlight('#x-lesson')"),
        ],
        "say": (
            "Question three. Does it get better? This is the tuning loop, the idea from Google Research's "
            "harness two. It reads the agent's own past runs, proposes changes, tests every one in a "
            "throwaway copy of the database, and keeps the cheapest version that still passes every check. "
            "Same model, same answers, [excited] thirty-seven percent fewer tokens per ticket. And it wrote "
            "down why, so the next round starts smarter."
        ),
    },
    {
        "id": "e07-vs",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(6)", "@pause:0.8"],
        "at": [
            (0.30, f"{D}.spotlight('#vs thead th:nth-child(3)')"),
            (0.52, f"{D}.spotlight('#vs-half')"),
            (0.60, f"{D}.spotlight('#vs-stop')"),
            (0.70, f"{D}.spotlight('#vs-learn')"),
            (0.80, f"{D}.spotlight('#vs-adopt')"),
            (0.90, f"{D}.spotlight('#vs-sys')"),
        ],
        "say": (
            "So why not just use harness two, plus whatever stack you already have? [thoughtful] Because "
            "harness two is a method, and a good one. It tunes an agent offline, against a benchmark, and "
            "hands you files. Wiring those into an app server, a vector store, a memory service and an eval "
            "tool, and keeping five systems agreeing about what happened, is your problem. Plexus runs the "
            "same method where the work happens. The run is a transaction. The veto sits where the data gets written. "
            "The tuning learns from your agent's real history, and adopting a change is an update, with the "
            "evidence attached. One system to secure, not five."
        ),
    },
    {
        "id": "e08-math",
        "pre": [f"{D}.clearSpot()", f"{D}.setSlider('wrong', 0, 10)", f"{D}.goto(7)", "@pause:0.8"],
        "at": [
            (0.10, f"{D}.spotlight('#inputs', 'assumptions: yours to set')"),
            (0.38, f"{D}.setSlider('wrong', 0.02, 1800)"),
            (0.44, f"{D}.spotlight('#out-exposure')"),
            (0.70, f"{D}.spotlight('#out-tokens')"),
        ],
        "say": (
            "And what's that worth? These are assumptions, so plug in your own. Two million tickets, one in "
            "five needs a refund decision, the average refund is forty-five dollars. If just two percent of "
            "those get decided under the wrong policy, that's about four point three million dollars a year "
            "exposed. That's what the as of check and the veto protect. And the tuning saving, measured in "
            "this demo, is worth about seven hundred thousand a year in model spend, at three dollars per "
            "million tokens."
        ),
    },
    {
        "id": "e09-close",
        "pre": [f"{D}.clearSpot()", f"{D}.goto(8)", "@pause:0.8"],
        "say": (
            "[warm] So that's the pitch. Agents you can actually put on the money. They can't leak, because "
            "the policy for that day is checked inside the transaction. They can explain themselves, because every "
            "decision is one query away. And they get cheaper, because they tune from their own history, "
            "with receipts. All of it, in one Postgres. [excited] Go try to break it."
        ),
        "after": ["@pause:2.0"],
    },
]
