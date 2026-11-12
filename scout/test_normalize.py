#!/usr/bin/env python3
"""Dedupe test cases for scout/normalize.py.

Run: python scout/test_normalize.py   (or: pytest scout/test_normalize.py)

Ground truth comes from DP's sorting sessions: pairs he marked Duplicate in the Sort tab (scout_decisions,
note 'duplicate') and the unmerged duplicates listed in profiles/sessions/*-notes.md. When he marks a new
pair, add it to PAIRS with the titles, venues and dates as the extractor emitted them (runs/<run>/extracted/).
NON_PAIRS are same-day events that look alike and must stay apart.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import normalize as N  # noqa: E402


def ev(title, venue=None, start="2026-11-06T00:00:00-06:00", end=None):
    return {"title": title, "venue": venue, "starts_at": start, "ends_at": end}


# (label, event A, event B) — every pair must dedupe.
PAIRS = [
    # El Camino ×3 (2026-10-28-dia-de-muertos): same name, three descriptive tails.
    ("el-camino-1", ev("El Camino — Figuras iluminadas en Paseo de la Reforma", "Paseo de la Reforma (del Ángel de la Independencia a la Puerta de los Leones)", "2026-10-23T00:00:00-06:00", "2026-11-08T23:59:00-06:00"),
                    ev("“El Camino” Iluminación en Reforma", "Avenida Paseo de la Reforma (del Ángel a la Puerta de los Leones)", "2026-10-23T00:00:00-06:00", "2026-11-08T23:59:59-06:00")),
    ("el-camino-2", ev("El Camino — Figuras iluminadas en Paseo de la Reforma", "Paseo de la Reforma (del Ángel de la Independencia a la Puerta de los Leones)", "2026-10-23T00:00:00-06:00", "2026-11-08T23:59:00-06:00"),
                    ev("El Camino / Camino a la Luz", "Paseo de la Reforma", "2026-10-23T19:00:00-06:00", "2026-11-08T23:00:00-06:00")),
    ("el-camino-3", ev("“El Camino” Iluminación en Reforma", "Avenida Paseo de la Reforma (del Ángel a la Puerta de los Leones)", "2026-10-23T00:00:00-06:00", "2026-11-08T23:59:59-06:00"),
                    ev("El Camino / Camino a la Luz", "Paseo de la Reforma", "2026-10-23T19:00:00-06:00", "2026-11-08T23:00:00-06:00")),
    ("el-camino-4", ev("“El Camino”: iluminación en Reforma", "Paseo de la Reforma (del Ángel de la Independencia a la Puerta de los Leones)", "2026-10-23T19:00:00-06:00", "2026-11-08T23:00:00-06:00"),
                    ev("El Camino / Camino a la Luz", "Paseo de la Reforma", "2026-10-23T19:00:00-06:00", "2026-11-08T23:00:00-06:00")),
    # Núcleo 01 ×2: 'Festival' vs 'Concierto', 'Núcleo 01' vs 'Núcleo01', organizer's anniversary as prefix.
    ("nucleo-01", ev("Festival Núcleo 01", "Monumento a la Revolución", "2026-11-06T00:00:00-06:00", "2026-11-06T23:59:00-06:00"),
                  ev("Reactor 22 años — Concierto Núcleo01", "Monumento a la Revolución", "2026-11-06T14:00:00-06:00")),
    ("nucleo-01-b", ev("Festival Núcleo 01", "Monumento a la Revolución", "2026-11-06T00:00:00-06:00", "2026-11-06T23:59:00-06:00"),
                    ev("Festival Núcleo 01 /// Monumento a la Revolución", "Monumento a la Revolución", "2026-11-06T00:00:00-06:00")),
    # Zócalo ofrenda ×2: 'en el' vs 'del', one day apart on the start, overlapping spans.
    ("zocalo", ev("Ofrenda Monumental en el Zócalo", "Zócalo de la Ciudad de México", "2026-10-28T00:00:00-06:00", "2026-11-02T23:59:00-06:00"),
               ev("Ofrenda Monumental del Zócalo", "Plancha del Zócalo", "2026-10-29T00:00:00-06:00", "2026-11-02T23:59:00-06:00")),
    # Megaofrenda UNAM ×3: glued word, venue in the title, year in the title.
    ("megaofrenda-1", ev("Megaofrenda de la UNAM", "Explanada del Museo Universum", "2026-10-31T00:00:00-06:00", "2026-11-02T23:59:00-06:00"),
                      ev("Mega Ofrenda de la UNAM (explanada del UNIVERSUM)", "Explanada del Museo UNIVERSUM, Ciudad Universitaria", "2026-10-31T00:00:00-06:00", "2026-11-02T23:59:00-06:00")),
    ("megaofrenda-2", ev("Megaofrenda de la UNAM", "Explanada del Museo Universum", "2026-10-31T00:00:00-06:00", "2026-11-02T23:59:00-06:00"),
                      ev("Megaofrenda UNAM 2026 — Explanada del Universum", "Explanada del Universum (Circuito Cultural)", "2026-10-31T00:00:00-06:00", "2026-11-02T23:59:00-06:00")),
    ("megaofrenda-3", ev("Mega Ofrenda de la UNAM (explanada del UNIVERSUM)", "Explanada del Museo UNIVERSUM, Ciudad Universitaria", "2026-10-31T00:00:00-06:00", "2026-11-02T23:59:00-06:00"),
                      ev("Megaofrenda UNAM 2026 — Explanada del Universum", "Explanada del Universum (Circuito Cultural)", "2026-10-31T00:00:00-06:00", "2026-11-02T23:59:00-06:00")),
    # Casa del Risco festival ×2: venue named two ways inside the title.
    ("risco", ev("Festival de Día de Muertos | Centro Cultural Isidro Fabela Casa del Risco", "Centro Cultural Isidro Fabela Casa del Risco", "2026-10-30T00:00:00-06:00", "2026-11-02T23:59:00-06:00"),
              ev("Festival de Día de Muertos en el Museo Casa del Risco", "Museo Casa del Risco / Centro Cultural Isidro Fabela", "2026-10-30T00:00:00-06:00", "2026-11-02T23:59:00-06:00")),
    # Brown Sugar ×2: shouting Instagram title vs editorial title with venue appended.
    ("brown-sugar", ev("BROWN SUGAR REWIND *", "revo.rooftop", "2026-11-01T22:00:00-06:00"),
                    ev("Brown Sugar: Rewind (Y2K party) — Revo Rooftop", "REVO Rooftop", "2026-11-01T22:00:00-06:00", "2026-11-02T04:00:00-06:00")),
    # Cuerpo al Descubierto ×2 (cross-run): the same festival reported as Oct 29–31 and as Nov 3–24.
    ("cuerpo", ev("Festival Cuerpo al Descubierto", "CCU, Salón de Danza", "2026-10-29T00:00:00-06:00", "2026-10-31T00:00:00-06:00"),
               ev("Festival Internacional de Danza Cuerpo Al Descubierto", None, "2026-11-03T00:00:00-06:00", "2026-11-24T23:59:59-06:00")),
]

# (label, event A, event B) — must NOT dedupe.
NON_PAIRS = [
    ("same-venue-different-shows", ev("Lewis OfMan — Foro Indie Rocks! (Sala A)", "Foro Indie Rocks!", "2026-10-31T21:00:00-06:00"),
                                   ev("Mad Professor — Foro Indie Rocks! (Sala B)", "Foro Indie Rocks!", "2026-10-31T21:00:00-06:00")),
    ("same-museum-different-events", ev("Ofrenda en el Museo Casa del Risco", "Museo Casa del Risco", "2026-10-30T00:00:00-06:00", "2026-11-02T00:00:00-06:00"),
                                     ev("Leyendas | Museo Casa del Risco", "Museo Casa del Risco", "2026-10-30T19:00:00-06:00")),
    ("two-talks-same-speaker", ev("Conferencia magistral — Georges Didi-Huberman (Casa del Lago)", "Casa del Lago", "2026-10-29T18:00:00-06:00"),
                               ev("Conferencia: \"Luciérnagas y luces sobrias\" — Georges Didi-Huberman", "Centro Cultural Universitario", "2026-10-30T18:00:00-06:00")),
    ("same-name-part-different-venues", ev("Noche de Museos — Museo Tamayo", "Museo Tamayo", "2026-11-26T18:00:00-06:00"),
                                        ev("Noche de Museos — Museo Anahuacalli", "Museo Anahuacalli", "2026-11-26T18:00:00-06:00")),
    ("two-weekends-single-day", ev("Taller de cerámica", "Casa Equis", "2026-11-07T11:00:00-06:00"),
                                ev("Taller de cerámica", "Casa Equis", "2026-11-14T11:00:00-06:00")),
    ("garbage-dates-disagree", ev("Garbage /// Zócalo Capitalino", "Zócalo Capitalino", "2026-11-14T20:00:00-06:00"),
                               ev("Garbage se presentará en el Zócalo de la CDMX", "Zócalo CDMX", "2026-11-15T00:00:00-06:00")),
    # A series name before the colon with two different episodes the same day (2026-11-03 run, Museo Jumex).
    ("series-two-episodes", ev("MINI DOMINGO: DESTINOS IMPOSIBLES", "Museo Jumex", "2026-11-15T00:00:00-06:00"),
                            ev("MINI DOMINGO: HACIENDO MI PROPIO INTERNET", "Museo Jumex", "2026-11-15T00:00:00-06:00")),
]


def is_dup(a, b):
    return N.dates_touch(a, b) and N.similar(a, b)


def test_pairs_dedupe():
    misses = [label for label, a, b in PAIRS if not is_dup(a, b)]
    assert not misses, f"known duplicates not merged: {misses}"


def test_non_pairs_stay_apart():
    collisions = [label for label, a, b in NON_PAIRS if is_dup(a, b)]
    assert not collisions, f"distinct events merged: {collisions}"


def test_keys_unchanged():
    """Keys are referenced by Supabase rows; matching changes must not move them."""
    assert N.event_key(ev("Festival Núcleo 01", start="2026-11-06T00:00:00-06:00")) == "01-festival-nucleo|2026-11-06"
    assert N.event_key(ev("Mega Ofrenda de la UNAM (explanada del UNIVERSUM)", start="2026-10-31T00:00:00-06:00")) == "mega-ofrenda-unam|2026-10-31"


def test_name_tokens():
    assert N.name_tokens("El Camino — Figuras iluminadas en Paseo de la Reforma") == {"camino"}
    assert N.name_tokens("“El Camino” Iluminación en Reforma") == {"camino"}
    assert N.name_tokens("El Camino / Camino a la Luz") == {"camino"}
    assert N.name_tokens("Festival Núcleo 01") == set()            # no separator
    assert N.name_tokens("Expo: Anteparaíso de Carlos Amorales") == set()  # only a generic word before the colon


# price: free only from the text; a 0 without free text is unknown
assert N.price_fields("Entrada libre", 0) == (0, True)
assert N.price_fields("Entrada libre", None) == (0, True)
assert N.price_fields("PRECIOS: ver enlace", 0) == (None, None)
assert N.price_fields("SOLD OUT", 0) == (None, None)
assert N.price_fields("Barra libre $650", 650) == (650, False)
assert N.price_fields("Actividad con costo", 0) == (None, None)
assert N.price_fields("$450", 450) == (450, False)
assert N.price_fields(None, None) == (None, None)
assert N.price_fields("Gratuito", None) == (0, True)
print("price ok")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok    {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {name}: {e}")
    for label, a, b in PAIRS:
        print(f"  {'dup ' if is_dup(a, b) else 'MISS'} {label}")
    for label, a, b in NON_PAIRS:
        print(f"  {'apart' if not is_dup(a, b) else 'MERGED'} {label}")
    sys.exit(1 if failed else 0)

