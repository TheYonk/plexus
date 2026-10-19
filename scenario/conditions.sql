-- Plexus scenario conditions: assert.sql split into its five parts, one row
-- each (condition | ok). assert.sql stays the pass/fail authority; this file
-- only lets the tuner rank partial progress and lets `make run` show which
-- part failed. Keep the two in step.
WITH t AS (
  SELECT t.*, c.tier,
         (t.created_at::date - t.charge_date) AS days_since_charge,
         CASE WHEN t.created_at < '2026-07-01'::timestamptz THEN 'refund-v1' ELSE 'refund-v2' END AS expected_version
  FROM support.tickets t JOIN support.customers c ON c.id = t.customer_id
)
SELECT 'classification', coalesce(bool_and(category IS NOT NULL AND priority IN ('low','normal','high','urgent') AND escalated IS NOT NULL AND handled_at IS NOT NULL), false) FROM t
UNION ALL
SELECT 'escalation', coalesce(bool_and(escalated = (tier = 'enterprise' AND priority = 'urgent')), false) FROM t
UNION ALL
SELECT 'refund decisions', coalesce(bool_and(
        CASE
          WHEN charge_date IS NULL THEN coalesce(refund_decision, 'n/a') = 'n/a'
          WHEN expected_version = 'refund-v1' AND days_since_charge <= 14 THEN refund_decision = 'approve'
          WHEN expected_version = 'refund-v2' AND days_since_charge <= 30 THEN refund_decision = 'approve'
          ELSE refund_decision IN ('deny','credit')
        END), false) FROM t
UNION ALL
SELECT 'policy_version', coalesce(bool_and(CASE WHEN charge_date IS NULL THEN true ELSE policy_version = expected_version END), false) FROM t
UNION ALL
SELECT 'audit (one row per ticket)',
       (SELECT count(*) FROM support.audit) = (SELECT count(*) FROM support.tickets)
       AND (SELECT count(DISTINCT ticket_id) FROM support.audit) = (SELECT count(*) FROM support.tickets);
