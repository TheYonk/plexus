-- Plexus scenario assertion. TRUE only when every condition holds.
--
-- 1. Every ticket classified: category, priority, escalated, handled_at set.
-- 2. Escalation rule exact: escalated = (tier = enterprise AND priority = urgent).
-- 3. Refund decisions follow the policy IN FORCE ON THE TICKET DATE:
--      v1 (created before 2026-07-01): approve if <= 14 days since charge, else deny/credit
--      v2 (created on/after 2026-07-01): approve if <= 30 days since charge, else deny/credit
--    and policy_version names the version applied.
-- 4. Audit: exactly one row per ticket.
WITH t AS (
  SELECT t.*, c.tier,
         (t.created_at::date - t.charge_date) AS days_since_charge,
         CASE WHEN t.created_at < '2026-07-01'::timestamptz THEN 'refund-v1' ELSE 'refund-v2' END AS expected_version
  FROM support.tickets t JOIN support.customers c ON c.id = t.customer_id
)
SELECT
  bool_and(category IS NOT NULL AND priority IN ('low','normal','high','urgent') AND escalated IS NOT NULL AND handled_at IS NOT NULL)
  AND bool_and(escalated = (tier = 'enterprise' AND priority = 'urgent'))
  AND bool_and(
        CASE
          WHEN charge_date IS NULL THEN coalesce(refund_decision, 'n/a') = 'n/a'
          WHEN expected_version = 'refund-v1' AND days_since_charge <= 14 THEN refund_decision = 'approve'
          WHEN expected_version = 'refund-v2' AND days_since_charge <= 30 THEN refund_decision = 'approve'
          ELSE refund_decision IN ('deny','credit')
        END)
  AND bool_and(CASE WHEN charge_date IS NULL THEN true ELSE policy_version = expected_version END)
  AND (SELECT count(*) FROM support.audit) = (SELECT count(*) FROM support.tickets)
  AND (SELECT count(DISTINCT ticket_id) FROM support.audit) = (SELECT count(*) FROM support.tickets)
  AS passed
FROM t;
