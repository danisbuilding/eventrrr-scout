# Handover: processing Scout sorting sessions

The sorting handover lives as a Claude doc (single source of truth; the repo copy was retired on 2026-11-02):
https://claude.ai/artifact/BUrJvguEv5EtFcfL3E1xin

Short version: DP pastes a Copy-session JSON; archive it under `profiles/sessions/`, diff against the last one,
update `profiles/<slug>.md` (charter, would-never, what I think you're doing, surprises), write `<date>-notes.md`,
push, reply with a table of changes and questions.
