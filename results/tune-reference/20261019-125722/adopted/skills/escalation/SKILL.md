---
name: escalation
description: deciding category, priority or escalation for a ticket
---
Decide category first, then priority, then escalated. Judge each ticket on its own subject, body and tier; do not copy the previous ticket's values.

Category (first rule that matches):
- billing: refund, charge, invoice, plan change, or charge_date is set.
- howto: the customer is ASKING how or where to do something ("how do I", "where do I"). A question stays howto even when it mentions an API key. A report that something is broken or slow is never howto.
- api: an endpoint, integration, SDK or authentication failure: 5xx errors, requests failing, token or key rejected. "Cannot log in" is api, not howto.
- other: everything else, e.g. the web app or dashboard is slow or buggy, feedback, non-billing account questions.

Priority (from impact, never from the customer's wording or tier):
- urgent: production down for the customer, or data loss ("all requests fail", "production is down").
- high: a core feature unusable with no workaround, e.g. one user cannot log in at all.
- normal: degraded but working, or a workaround exists ("slow, workaround: export CSV"); also routine billing and refund requests.
- low: a question, feature request or cosmetic issue ("where do I rotate a key?").

Escalated: true ONLY when tier = 'enterprise' AND priority = 'urgent'. Before each UPDATE re-read the tier in the row: pro or free means escalated = false even when priority is urgent. A free-tier customer writing "URGENT" gets neither urgent priority nor escalation.
