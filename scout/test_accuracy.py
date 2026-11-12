#!/usr/bin/env python3
"""Tests for the comparison rules in accuracy.py (no network, no database)."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accuracy import compare, focus_text, TZ  # noqa: E402


def ev(local, all_day=False):
    return {"starts_at": dt.datetime.fromisoformat(local).replace(tzinfo=TZ), "all_day": all_day}


def ans(date, time=None, conf="high", found=True, others=(), free=None, pmin=None):
    return {"found": found, "date": date, "start_time": time, "other_dates": list(others), "evidence": "x", "confidence": conf,
            "page_free": free, "page_price_min": pmin}


def names(flags):
    return [f[0] for f in flags]


# Garbage: Scout had Sunday 15 all day, the page says Saturday 14 at 20:00
f = compare(ev("2026-11-15 00:00", True), ans("2026-11-14", "20:00"))
assert names(f) == ["date_mismatch"] and f[0][1] == "demote", f
assert f[0][3] == dt.datetime(2026, 11, 14, 20, 0, tzinfo=TZ)
# right day, all-day stored, page has a time
f = compare(ev("2026-11-14 00:00", True), ans("2026-11-14", "20:00"))
assert names(f) == ["time_found"] and f[0][3].hour == 20, f
# right day and time (within 30 min)
assert compare(ev("2026-11-14 20:00"), ans("2026-11-14", "20:30")) == []
# time off by an hour
assert names(compare(ev("2026-11-14 20:00"), ans("2026-11-14", "21:00"))) == ["time_mismatch"]
# multi-date event: the stored date is one of the page's dates
assert compare(ev("2026-11-21 00:00", True), ans("2026-11-20", None, others=["2026-11-21"])) == []
# low confidence or not found never flags here
assert compare(ev("2026-11-15 00:00", True), ans("2026-11-14", conf="low")) == []
assert compare(ev("2026-11-15 00:00", True), ans(None, found=False)) == []
# 8 pm in CDMX is the next day in UTC: no false mismatch
e = {"starts_at": dt.datetime(2026, 11, 15, 2, 0, tzinfo=dt.timezone.utc), "all_day": False}
assert compare(e, ans("2026-11-14", "20:00")) == []
# long listing pages are cut to windows around the title, accents and all
page = ("relleno " * 3000) + "Sábado 14 de noviembre: Garbage en el Zócalo, 20:00 h. " + ("más relleno " * 3000)
out = focus_text(page, "Garbage se presentará en el Zócalo de la CDMX", limit=6000)
assert "Garbage en el Zócalo, 20:00" in out and len(out) <= 6100, len(out)
# prices: "PRECIOS: ver enlace" stored as free, page lists MX$450 → mismatch; unknown + page free → found
pe = {**ev("2026-11-11 20:00"), "price_text": "PRECIOS: ver enlace", "price_min": 0}
f = compare(pe, ans("2026-11-11", "20:00", free=False, pmin=450))
assert names(f) == ["price_found"] and f[0][2]["page_price_min"] == 450, f
pe = {**ev("2026-11-11 20:00"), "price_text": "Entrada libre", "price_min": 0}
assert names(compare(pe, ans("2026-11-11", "20:00", free=False, pmin=450))) == ["price_mismatch"]
pe = {**ev("2026-11-11 18:00"), "price_text": None, "price_min": None}
f = compare(pe, ans("2026-11-11", "18:00", free=True))
assert names(f) == ["price_found"] and f[0][2]["page_free"] is True, f
pe = {**ev("2026-11-11 20:00"), "price_text": "$450", "price_min": 450}
assert compare(pe, ans("2026-11-11", "20:00", free=False, pmin=460)) == []
print("accuracy tests passed")
