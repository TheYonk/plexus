---
source_id: policy:escalation
version_label: escalation-2026
effective_from: 2026-01-01
---
# Escalation matrix (2026)

A ticket is escalated to the on-call engineer when, and only when, the customer
is on the enterprise tier AND the ticket priority is urgent. Every other
combination stays in the normal queue: enterprise + high is not escalated;
pro + urgent is not escalated; free + urgent is not escalated.

Priority guide: urgent = production down or data loss; high = a core feature
unusable with no workaround; normal = degraded but working; low = question,
feature request, or cosmetic.

Category guide: api = integration, SDK, endpoint or authentication problems;
billing = charges, invoices, refunds, plan changes; howto = usage questions;
other = anything else.
