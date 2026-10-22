"""Record what the deck's live slides show, for the static site.

Reads the harness, the audit chain for ticket 104 and the tuning numbers
from the running API, and runs the live policy change once for real
(refund under v2, publish v3, the same refund under v3, the July ticket).
Writes site/deck-snapshot.json; site/build.py puts it into the static deck,
which replays it. The policy is reset to v2 afterwards.

    api/.venv/bin/python demo/snapshot.py [--url http://127.0.0.1:8766/]
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "deck-snapshot.json"


def call(url: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url.rstrip("/") + path, method="GET" if body is None else "POST")
    if body is not None:
        req.add_header("content-type", "application/json")
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766/")
    url = ap.parse_args().url
    snap = {
        "recorded": datetime.date.today().isoformat(),
        "harness": call(url, "/ui/harness"),
        "audit": call(url, "/exec/audit/104"),
        "numbers": call(url, "/exec/numbers"),
    }
    call(url, "/deck/policy/reset", {})
    try:
        policy = {"before": call(url, "/deck/policy/try", {"case": "oct", "label": "before"})}
        policy["publish"] = call(url, "/deck/policy/publish", {})
        policy["after"] = call(url, "/deck/policy/try", {"case": "oct", "label": "after"})
        policy["jul"] = call(url, "/deck/policy/try", {"case": "jul", "label": "jul"})
    finally:
        call(url, "/deck/policy/reset", {})
    ok = policy["before"]["landed"] and not policy["after"]["landed"] and policy["jul"]["landed"]
    for k in ("before", "after", "jul"):
        r = policy[k]
        print(f"  {k:6s} {'committed' if r['landed'] else 'rejected'} under {r['in_force']} in {r['seconds']}s {r['error'] or ''}")
    if not ok:
        raise SystemExit("the policy change did not come out as the deck tells it; not writing a snapshot (run it again)")
    snap["policy"] = policy
    OUT.write_text(json.dumps(snap, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
