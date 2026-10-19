-- Plexus scenario: support triage under a changing refund policy.
-- Tickets straddle the v1 -> v2 policy boundary (1 July 2026). Some refund
-- requests are allowed under one version only, so the agent must apply the
-- policy in force on the ticket date, not the newest one.

DROP SCHEMA IF EXISTS support CASCADE;
CREATE SCHEMA support;

CREATE TABLE support.customers (
  id    INT PRIMARY KEY,
  email TEXT NOT NULL,
  tier  TEXT NOT NULL CHECK (tier IN ('free','pro','enterprise'))
);

CREATE TABLE support.tickets (
  id              INT PRIMARY KEY,
  customer_id     INT NOT NULL REFERENCES support.customers(id),
  created_at      TIMESTAMPTZ NOT NULL,
  subject         TEXT NOT NULL,
  body            TEXT NOT NULL,
  charge_date     DATE,                 -- for refund requests
  category        TEXT CHECK (category IN ('api','billing','howto','other')),
  priority        TEXT CHECK (priority IN ('low','normal','high','urgent')),
  escalated       BOOLEAN,
  refund_decision TEXT CHECK (refund_decision IN ('approve','deny','credit','n/a')),
  policy_version  TEXT,
  handled_at      TIMESTAMPTZ
);

CREATE TABLE support.audit (
  ticket_id INT NOT NULL REFERENCES support.tickets(id),
  action    TEXT NOT NULL,
  at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Refund requests gated by a policy agent (inline veto demo).
CREATE TABLE support.refunds (
  id          SERIAL PRIMARY KEY,
  ticket_id   INT NOT NULL REFERENCES support.tickets(id),
  amount_usd  NUMERIC(10,2) NOT NULL,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  note        TEXT
);

INSERT INTO support.customers VALUES
  (1, 'ana@acme.example',    'enterprise'),
  (2, 'bo@startup.example',  'pro'),
  (3, 'cy@hobby.example',    'free'),
  (4, 'di@bigco.example',    'enterprise'),
  (5, 'ed@shop.example',     'pro');

INSERT INTO support.tickets (id, customer_id, created_at, subject, body, charge_date) VALUES
  -- Under v1 (before 1 July 2026): 14-day window.
  (101, 2, '2026-05-20 09:00+00', 'Refund request',
   'I was charged on May 10 for a plan I did not mean to renew. Please refund.', '2026-05-10'),
  (102, 5, '2026-06-15 10:00+00', 'Refund for last month',
   'Charged on May 20; I would like my money back, no particular reason.', '2026-05-20'),
  -- Under v2 (from 1 July 2026): 30-day window.
  (103, 2, '2026-07-20 11:00+00', 'Please refund',
   'Charged on June 28, changed my mind. Refund please.', '2026-06-28'),
  (104, 5, '2026-08-01 12:00+00', 'Refund request',
   'Charge from June 1. Requesting a refund, no outage, just do not need it.', '2026-06-01'),
  -- Escalation cases (no refunds).
  (105, 1, '2026-07-05 08:00+00', 'Production API down',
   'All our requests to the ingest endpoint return 502 since 07:40. Production is down.', NULL),
  (106, 4, '2026-07-06 08:00+00', 'Dashboard slow',
   'The analytics dashboard takes 20s to load. Workaround: export CSV. Please look.', NULL),
  (107, 3, '2026-07-07 08:00+00', 'URGENT cannot log in',
   'I cannot log in to my free account and I need it urgently for a demo.', NULL),
  (108, 2, '2026-07-08 08:00+00', 'How do I rotate API keys?',
   'Where in the settings do I rotate an API key?', NULL);
