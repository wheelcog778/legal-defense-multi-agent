# Legal Defense Multi-Agent · v1.9.1

> A brief loses on the provision nobody read.

An 11-station adversarial pipeline for administrative-penalty defense under Chinese law:
facts → favorable authority → **adverse authority** → **case law** → **norm conflict** →
**concept genealogy** → arguments → **red team** → **citation check** → draft → gate.

Eleven Markdown role cards, three zero-dependency Python utilities, one 26-item submission gate — plus
one gate that is actually code (`gates/citegate.py`: every citation in the draft must have been marked
accurate in the citation table, or the document does not ship). It runs on a
[Hermes](https://hermes-agent.nousresearch.com/docs) kanban board — or, with the bundled manual, on any
chat model at all, with no tooling.

## The failure it is built around

A single model drafting a defense brief searches in one direction: for support. Real losses come
from the other direction.

- **The swap.** You build the whole brief on article 6 of one regulation. The agency answers with
  article 12 and article 22(3) of its implementing measures — a provision that fines the individual
  directly. Every paragraph you wrote is now about a norm that is not being applied, and re-reading
  your own draft cannot reveal it, because the draft never contained the other provision.
- **The drift.** The concept the case turns on was redefined between the old and the new version of
  the rule. Argue today's definition and the reply is that conduct is judged under the version in
  force at the time — *从旧兼从轻*, Article 37 of the Administrative Penalty Law.
- **The citation.** An article number remembered approximately, with a plausible revision year. One
  wrong article in the load-bearing paragraph makes the rest read as unserious, however good it is.

None of the three is visible to the chain that produced the draft. So each becomes its own station,
staffed by a different role, under a gate that is allowed to refuse the output.

## What is inside

| Path | What it does |
|---|---|
| `SKILL.md` | Entry point: when to use it, the card graph, the gate contract, pitfalls |
| `roles/00…60_*.md` | 11 role cards, each self-contained (role + inputs + required output shape) |
| `checklist.md` | The submission gate: table A (26 items, documents) and table B (12 items, "window closed" note) |
| `build_case.py` | Creates the DAG on a kanban board from `cases/<slug>/` |
| `run.sh` | Build + dispatch until nothing is ready |
| `preflight.py` | One command: role-card count, gate item counts, version sameness, case completeness |
| `gates/citegate.py` | The citation whitelist gate: every explicit citation in the draft is checked against the entries the citation table marked 准确. Stdlib only, runs on a case directory |
| `examples/citegate_demo/` | Fictional case that makes the gate fail on purpose — one allowed citation, one denied, one unverified |
| `render.py` | Markdown → print-ready HTML for the manual (zero dependencies) |
| `references/` | Four operating notes: deterministic gates, porting the skeleton, reviewing an existing brief, public decisions as test inputs |
| `manual/行政处罚申辩十道工序.pdf` | Ten self-contained prompts plus the gate — the no-tooling path, for any model |

## The card graph

```
00 facts (researcher)
├─ 10 favorable authority (researcher) ─┐
├─ 11 adverse authority  (analyst)   ───┤
└─ 12 case law            (analyst)   ──┤
                                        ├─ 15 norm conflict (verifier) ─┐
                                        └─ 16 concept genealogy (verifier) ─┴─ 20 arguments (analyst)
                                                                                 ├─ 30 red team (verifier)
                                                                                 └─ 40 citation check (verifier)
                                                                                        └─ 50 draft (writer)
                                                                                            └─ 60 gate (verifier)
```

`11` must name, on its first line, the provision the previous draft missed — listing provisions
without naming the miss means the station degraded into ordinary search and the run has zero
adversarial value.

## Run it

**Path 1 — any model, no tooling.** Read `manual/行政处罚申辩十道工序.pdf`, feed the ten prompts in
order to whatever model you have. Every prompt is self-contained; nothing says "see step above".

**Path 2 — Hermes kanban.**

```bash
python3 preflight.py                      # roles, gate counts, version, case completeness
mkdir -p cases/<slug>/input cases/<slug>/out
python3 build_case.py cases/<slug>        # needs assignees researcher/analyst/verifier/writer
bash run.sh cases/<slug>
```

`preflight.py --kanban` additionally checks that the four assignees exist on the board. The DAG is
idempotent: re-running `build_case.py` on a case that already has cards changes nothing.

## The one gate that is code

A model saying "I checked the citations" is not a check. `gates/citegate.py` is the version of that
claim turned into a function: it reads `out/citations.md` and the stage-appropriate draft, extracts
every explicit citation (`《规范》第X条第Y款第Z项`, including `及/、/和` lists, Chinese numerals and
table cells), and compares each one against the entries the citation table marked 准确.

```bash
python3 gates/citegate.py examples/citegate_demo
# status=fail fails=3 allowed=1
```

Three verdicts, and the difference matters: a citation the table marked as wrong is **denied**; a
citation the table never mentions is **unverified**; both count as fail. Missing table or missing
draft is `BLOCKED`, never `PASS` — unverified is unproven. Three exemptions are recorded but not
counted (quoting the agency's own citation, a citation the draft itself flags as unchecked, and the
appendix comparison table, which is checked as self-reported conflict instead).

What it deliberately does not do: it does not verify that the quoted text is verbatim correct — that
is the citation-check station's job — and it does not resolve pronouns like 该条例, which are
reported as unresolved rather than passed. See `references/deterministic-gates.md` for the wiring
order and the six dirty formats it has to parse.

## The gate

- **Two tables, chosen by output type.** Table A (26 items) for a brief or application; table B
  (12 items) for a "the window has closed" note. Picking the wrong table voids the gate.
- **Four verdicts.** `pass` / `fail` / `n/a` / `blocked`. `n/a` is only "this package does not contain
  that material"; `blocked` is "it should be checked and the channel is unavailable". The two are not
  interchangeable.
- **`fail 0` with `blocked > 0` is still not submittable.** Unverified is unproven.
- **The verdict line carries no soft landing.** No "can be filed as a first draft", no "basically
  submittable". Either `可提交（fail 0，阻断 0，blocked 0）` or `不可提交（fail n，阻断 B1/0，blocked k）`.
- **Deadlines are arithmetic, not prose.** Writing "60 days for reconsideration" is not checking the
  deadline; the gate fails it until the expiry date and the days remaining are computed from the
  service date.

## What this is not

- **Not validated against a baseline.** The A/B study is pre-registered with its kill criteria fixed
  before any data (detection-rate gap < 20 pp, false positives +15 pp, cost > 5× ⇒ "not useful"),
  and it has **not been run**. Nothing here supports the claim that this pipeline produces better
  briefs than one model writing one draft. That claim is the hypothesis, not the result.
- **Not reviewed by a lawyer.** 0 cases.
- **No case with a client's original documents.** 0. Every deadline conclusion reached during
  testing rests on a service date that we inferred ourselves.
- **What has actually been run:** four real, publicly published penalty decisions end to end during
  development, and three rounds of external testing by an independent agent on a different model to
  check portability. That shows the pipeline runs and can catch a real mis-citation. It does not show
  it is right on a case it has not seen — and those four cases were used while building it, so they
  are not held-out samples.
- **The citation gate parses patterns, not meaning.** It was calibrated against one real case during
  development. A citation phrased in a form its regex does not cover is invisible to it, so a `PASS`
  means "nothing it could see was out of bounds", not "the citations are correct".
- **Not a substitute for a lawyer, and not legal advice.** The windows are short — statement and
  defense, reconsideration within 60 days, litigation within 6 months — and a wrong stage call wastes
  the entire document. Determine the stage before writing a word.
- **Chinese administrative law only.** The skeleton ports to other rule-bound domains
  (`references/framework-porting.md`); the content does not.

## Who it is for

- Someone holding a 告知书 or 决定书 who wants the adverse case mapped before drafting anything.
- A team that already writes these briefs and wants the adversarial stations as a checklist.

Not for: general legal Q&A, a one-page letter, or anyone who needs a document today without reading
the gate.

## License

MIT. See `LICENSE`. This repository is a method, not legal advice, and carries no warranty.