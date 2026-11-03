#!/usr/bin/env python3
"""Keep the Scout IQ Supabase project awake: the free plan pauses after 7 idle days.

Usage: python scout/iq_keepalive.py [--days 5]
If nothing has been written to runs, observations or heartbeats in the last N days, insert a heartbeats row.
Needs SCOUT_IQ_DB_URL (the scout_pipeline role). Runs weekly from .github/workflows/keepalive.yml.
"""
import argparse
import os
import sys

import psycopg

KEEPALIVE_DAYS = 5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=KEEPALIVE_DAYS)
    a = ap.parse_args()
    url = os.environ.get("SCOUT_IQ_DB_URL", "").strip()
    if not url:
        print("SCOUT_IQ_DB_URL not set", file=sys.stderr)
        sys.exit(1)
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("""select greatest((select max(created_at) from runs), (select max(created_at) from observations),
                                       (select max(created_at) from heartbeats))""")
        last = cur.fetchone()[0]
        cur.execute("select now() - make_interval(days => %s)", (a.days,))
        cutoff = cur.fetchone()[0]
        if last and last > cutoff:
            print(f"last write {last:%Y-%m-%d %H:%M}, within {a.days} days: nothing to do")
            return
        cur.execute("insert into heartbeats (note) values (%s)", (f"keepalive: no write since {last:%Y-%m-%d}" if last else "keepalive: first",))
        conn.commit()
        print(f"heartbeat written (last write: {last or 'never'})")


if __name__ == "__main__":
    main()
