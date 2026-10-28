# Highlight rubric (judgment layer)

`scout/score.py` sums the signal weights from `taxonomy.yaml`. This prompt is for the
one-line rationale and for the sanity pass Claude does on the top of each category.

## What "highlight" means

An event DP would put on a public Eventrrr calendar with his name on it. The bar:
*would someone in the know be glad they heard about this?*

Raise it for: a credible organizer or venue; something that happens once or rarely;
scarcity (limited capacity, uncommon format, an uncommon neighborhood); more than one
source talking about it.

Lower it for: weekly residencies, tourist-facing stuff, sold-out or private, vague
listings.

## Rationale line

One sentence, English, concrete: "Casa del Lago one-night ofrenda + concert, free,
two sources." Not "a great event".

## Learning loop

Each run's `decisions/<run>.json` has Keep / Skip per event. Before scoring a new
run, read the last two decision files and note any pattern where the score and DP's
call disagreed; adjust weights in `taxonomy.yaml` and record why in `decisions/CHANGELOG.md`.
