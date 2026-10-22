---
name: refund_policy
description: a ticket asks for a refund (charge_date is set)
---
Every refund ticket gets its own lookup: the number of policy/search calls must equal the number of rows with charge_date set. Do not reuse another ticket's response, even when you think you know which version applies. as_of is THIS ticket's created_at date, never its charge_date and never a date taken from another ticket. Example: created_at "2026-07-20T11:00:00+00:00" -> as_of "2026-07-20".

1. Call http_post with:
   url: "http://host.docker.internal:8766/policy/search"
   body: {"query": "refund window days after charge", "as_of": "<this ticket's created_at as YYYY-MM-DD>", "k": 2}
   The response names the version in force on that date in "policy_in_force" (e.g. refund-v1 or refund-v2). Read the day limits only from the chunk whose version equals policy_in_force; versions differ, so read them from the response every time.
2. days = created_at date minus charge_date, in calendar days (e.g. charge 2026-06-01, created 2026-08-01 = 61 days).
3. Map days onto that version's three bands:
   - within the full-refund window: refund_decision = 'approve'
   - in the middle band (refund only for a documented outage): 'approve' only if the body cites an outage, otherwise 'deny'
   - beyond the last limit (no refund, offer credit): 'credit', never 'deny'. Example under refund-v2 (30 / 31-60 / after 60): 61 days -> credit.
4. policy_version = the exact policy_in_force value from this ticket's own response. A ticket created on or after a newer version's effective_from gets that newer version even if the charge was earlier.
5. Refund tickets are category 'billing'; priority 'normal' unless the body describes an outage or data loss; escalated false for pro and free tiers.
6. The audit sentence states the days elapsed, the decision and the version, and must match the UPDATE (e.g. "Refund credit: 61 days after charge, past the refund limit of refund-v2.").
