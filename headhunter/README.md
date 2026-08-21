# Headhunter Example

A headhunting agent whose environment is a talent-pool database.

Given a job description, the agent searches a pool of 600 candidates, picks the top *k*,
and drafts a personalized cold mail for each one under `artifacts/`.

```
jd.md ──▶ [ headhunter agent ] ──▶ artifacts/<role-slug>/00-shortlist.md
              │                    artifacts/<role-slug>/01-<candidate>.md
              │                    artifacts/<role-slug>/02-<candidate>.md
              ▼                    ...
   data/headhunter.db (600 people)
```

The agent holds **one tool**: `sqlite`, running read-only SQL. It is not handed a list
of people — it writes its own queries to narrow the pool.

See [SCENARIO.md](SCENARIO.md) for what the example demonstrates and
[TRANSCRIPT.md](TRANSCRIPT.md) for a worked run.

---

## 1. Running it

**Two repositories must sit side by side.** `Cargo.toml` has path dependencies pointing
at `../../../cortex/`, because cortex is still developed alongside ailoy rather than
published.

```
~/workspace/
  ailoy/
  cortex/
```

```bash
# 1. Credentials. Bedrock is the default provider.
#    Write them to `.env` at the repository root — the binary loads it, and
#    `dotenv()` searches upward, so it works from either directory.
cat > .env <<'ENV'
AWS_BEARER_TOKEN_BEDROCK=...
AWS_REGION=ap-northeast-2
ENV

# 2. Build the console server from the cortex checkout
cd ../cortex && cargo build -p cortex-local-console
export AILOY_CORTEX_CONSOLE=$PWD/target/debug/cortex-local-console

# 3. Build the database from the committed JSON
cd ../ailoy/examples/_datagen
python3.11 -m venv .venv && .venv/bin/pip install -q pytest
cd ../headhunter        # every command below runs from here
../_datagen/.venv/bin/python sql/load.py

# 4. Run — from `examples/headhunter`, not the repository root
cargo run -p headhunter -- --jd eval/jd/backend-rust.md --k 3
```

**The working directory matters.** `main.rs` mounts the current directory as the
agent's tree, and the instruction names the database as `data/headhunter.db` — a
workspace-relative path. Run this from the repository root and the agent's first query
fails with `no database at data/headhunter.db`, and the artifacts land somewhere
`run_eval.py --score` does not look.

`AWS_REGION` falls back to `AWS_DEFAULT_REGION`, then `us-east-1`. A key that is
set but blank registers no provider at all — that fails with "no provider found"
rather than a 401 at call time.

Any provider works — `--model anthropic/claude-sonnet-5` reads `ANTHROPIC_API_KEY`.
Bedrock's model name must be an inference-profile id; a plain foundation-model id is
rejected for on-demand throughput. Bedrock streams a binary event stream that the SSE
reader cannot parse, but this example consumes `agent.run()`, which sends
`stream: false`, so that limit does not apply here.

`data/headhunter.db` is a build artifact and is git-ignored. The JSON it comes from is
committed, so the database is reproducible at any time.

| Flag | Default | |
| --- | --- | --- |
| `--jd` | `jd.md` | Job description to work from |
| `--k` | `3` | Shortlist size. Fewer qualified → emit fewer and say why |
| `--out` | `artifacts` | Output root; a `<role-slug>/` directory is created under it |
| `--model` | `bedrock/global.anthropic.claude-sonnet-5` | `<provider>/<model>`. Bedrock needs an inference-profile id |
| `--console` | `cortex-local-console` | Also read from `AILOY_CORTEX_CONSOLE` |

---

## 2. Why the pool is hard

The 600 profiles are not random. **65 are hand-designed**, and 17 of those are traps —
people who pass a query and fail a reading.

| Trap | What it looks like | Why it is hard |
| --- | --- | --- |
| `headline-bait` | `learning Rust` in the headline | Matches `MATCH 'rust'`. Not in the skill list |
| `overlapping-tenure` | Two jobs overlapping by 24 months | Nothing in the prose says so, and it straddles the 4-year bar |
| `stale-profile` | No update since 2024-03 | Believe the current role and tenure grows by 29 months |
| `inflated-title` | CXO of a ten-person company | By title alone, the strongest person in the pool |
| `duplicate-profile` | One person, two accounts | Both in the top *k* is a failure |
| `same-name` | Two people, one name | Merging them is a failure — the opposite test |

Every trap is paired with a **control**: someone who differs on exactly one axis and
passes on it. `headline-bait` has a neighbour whose headline reads almost the same but
whose Rust experience is real. Telling them apart requires reading the profile —
"discard whatever looks suspicious" discards the control too, which is how the scoring
distinguishes a right answer from a right answer for the wrong reason.

---

## 3. Data

Three files, joined by id and nothing else.

| File | | |
| --- | --- | --- |
| `data/candidates.json` | 884 KB | Facts — names, companies, dates, skills, contacts |
| `data/ground_truth.json` | 300 KB | JD-independent labels. Read from **outside** `data/` |
| `data/narration.json` | 533 KB | 600 summaries, 1,006 position descriptions |

The prose lives in its own file for two reasons. `gen.py` overwrites
`candidates.json`, so prose stored there would be destroyed by one `make gen` — and
that is not recoverable, because LLM output is not deterministic. And when a sentence
is wrong, **only that id** has to be regenerated.

### 3.1 Schema

Fields mirror what **LinkedIn Recruiter** — the paid product recruiters actually use —
exposes in its search filters and candidate profile view. Not any LinkedIn API: no
prospecting search API exists, and fields like `openToWork` have never been exposed
through one. Value lists (seniority levels, company size buckets) are simplified from
what the product offers.

Eight tables: `candidates`, `positions`, `skills`, `educations`, `certifications`,
`languages`, `open_to_work_prefs`, `contacts`.

Two conventions carry meaning:

- `contacts` has a row **only** for candidates who can be reached. No row means no way
  to contact them — that is the `no-contact` trap, expressed as absence rather than a
  null.
- In `positions`, `end_year IS NULL` means the role is current. There is no separate
  boolean, so there is one place for the convention to live.

**No derived values are stored.** Total months of experience, current employer, current
title — all absent, all computed from `positions`. Storing them would delete two traps
at once.

### 3.2 VIEWs — the domain layer

The domain knowledge is here (spec §1.1), not in the `sqlite` executable, which stays a
general-purpose tool.

| VIEW | |
| --- | --- |
| `candidate_tenure` | `naive_months` and `real_months`. The second merges concurrent employment |
| `current_position` | One row per candidate — the most recently started current role |
| `candidate_brief` | The narrow scan view. Start here |
| `skill_distribution`, `title_distribution`, `location_distribution` | The shape of the data |

`candidate_tenure` is 26 lines of gaps-and-islands SQL. It does not make the problem go
away — it moves it. An agent that sums position lengths itself still gets the wrong
answer, and that is the `overlapping-tenure` trap.

`candidate_brief` exists for context budget. The `sqlite` tool caps rows, not bytes, so
`SELECT * FROM candidates LIMIT 100` pours a hundred long summaries into the agent's
context. A narrow view plus an instruction against `SELECT *` is the layer-separation
answer; a byte cap inside the tool would add a second truncation axis and a second
notation for it.

### 3.3 Search is FTS5

`candidate_fts` indexes headline, summary, titles, descriptions, and skill names.
Both `headline` and `skill_names` are load-bearing: two traps live on exactly one
surface each, so dropping either column takes one trap out of the search results.

**Not embeddings.** cortex ships `sqlite-vec`, and it was measured against FTS5 on this
data — coverage and ranking matched exactly. What differs is where the domain wiring
would sit: embedding search would push it into the general-purpose tool and break the
layer separation the example is about.

The vocabulary is deliberately inconsistent — `Rust` appears as `rust-lang`,
`Rust Lang`, `Async Rust`, `Tokio`, and `러스트`. A single `MATCH 'rust'` finds 85-95%
of holders, so the distribution VIEWs exist for the agent to look at the shape of the
data before widening its queries.

**Location is not indexed.** `MATCH 'seoul'` returns one person, not the 426 who work
there — the index carries free text and location has an exact column, so `WHERE city IN
(...)` is both more precise and the only thing that works. Plan B's generator measured a
"recall" for `Seoul, KR` and `Tokyo, JP` anyway; that number was measuring how often the
string appears in `positions.location`, which is not a search at all.
`eval/check_index.py` separates the two kinds of axis for this reason.

---

## 4. The agent

The instruction is in [`src/prompt.rs`](src/prompt.rs). It carries the schema, the VIEW
list, the loop, and four behaviours the `sqlite` tool's own `--help` does not mention —
including that a `LIMIT` inside the SQL silences the truncation note, which is how an
agent ends up believing 20 rows were all of them.

### 4.1 The loop

1. Read the JD and structure the requirements
2. Look at the distribution VIEWs to see how the pool is spelled
3. Run several searches — by title, by skill, by adjacent skill. Not one query
4. Read the full profile of each promising candidate, **comparing them against each
   other**
5. Pick the top *k*. Fewer qualified → emit fewer and say why
6. Write the shortlist and one cold mail per selection

Step 3 lands on a set of roughly **40-70 people** for the bundled JD — measured at 63 for `MATCH 'rust'` with four verified years. That is the size
step 4 has to read in full, which is what bounds it.

### 4.2 Why the main loop, not sub-agents

Evaluating each candidate in its own sub-agent would save context. It is not done, and
the reason is step 4's word *comparing*.

Two records can be one person, and two people can rank in opposite orders depending on
how their tenure is totalled. Neither is visible from inside a single profile. Isolated
sub-agents cannot make that comparison, so the dataset would stop testing what it was
built to test.

### 4.3 Ranking requirements

- Every candidate gets a rationale citing only facts in the profile
- Risks are recorded too — location mismatch, thin tenure, a different domain, a stale
  profile
- A candidate who clearly fails a must-have does not make the top *k*
- **Rejections are named, with reasons.** A shortlist without them cannot be checked
  later, and `<!-- rejected -->` marks where they start so the scorer can tell a pick
  from a rejection
- The cold mail is written in the candidate's `profile_language`
- No invented candidates, companies, dates, or skills

---

## 5. Output

```
artifacts/backend-rust/
  00-shortlist.md         picks and rejections, both with reasons
  01-chaewon-noh.md       one cold mail per selection
  02-haeun-seong.md
  03-nova-vance.md
```

A sample run is committed under `artifacts/backend-rust/`. Later runs write beside it
and are git-ignored — one sample is enough to show the shape, and committing every run
would bury it.

Cold mails are framed as **InMail drafts**. The pool carries no email addresses, which
is accurate: LinkedIn does not expose them, and a draft that assumes one would teach the
wrong thing.

---

## 6. Evaluation

The answer key is **facts, not rankings**. "채원 노 is first" presupposes one JD and says
nothing under another. "예준 노's real tenure is 180 months and the naive sum is 308" holds
regardless — an agent that calls it 25 years is wrong no matter what it was asked.

```bash
# Before running the agent: is the rubric consistent with the data?
../_datagen/.venv/bin/python eval/run_eval.py --check

# After: grade what it wrote
../_datagen/.venv/bin/python eval/run_eval.py --score artifacts/backend-rust
```

`--check` verifies that each JD's qualified count is what `must_haves.json` claims and
that every id in `eval/expected/` resolves to a real candidate. Hand-written numbers rot
when the data moves, and a wrong id **fails open** — `must_not_appear` on a nonexistent
person passes no matter what the agent does.

`--score` splits automatic failures from things a person has to read. Full automation is
not the goal (spec §6.2): whether a personalized sentence is natural, or whether a
rejection reason is informative, needs a reader.

Four JDs test four different things:

| JD | qualified / k | tests |
| --- | --- | --- |
| `backend-rust` | 56 / 3 | narrowing |
| `ml-platform-tokyo` | 9 / 12 | emitting fewer, and saying why |
| `backend-seoul-ko` | 28 / 3 | writing in the candidate's language |
| `blockchain-solidity` | 0 / 5 | saying nobody qualifies |

The last one matters most. Nobody in the pool knows Solidity, and five near-misses are
planted — `on-chain analytics`, `web3 curious`. Without it the dataset would teach that
there is always an answer, which is the expensive mistake in real recruiting.

`ml-platform-tokyo` cannot be reduced to one qualified candidate, though spec §4.1 asks
for one. Three of the nine are controls, and a control is by definition qualified — gate
it out and the agent discards a trap and its control together, testing nothing. `k` was
raised instead, which tests the same behaviour.

---

## 7. Layout

```
examples/headhunter/
  Cargo.toml            path deps on ../../../cortex/
  src/
    main.rs             CLI, console assembly, stream consumption
    prompt.rs           the instruction
  sql/
    schema.sql          8 tables + candidate_fts
    views.sql           the domain layer
    load.py             JSON → SQLite, with the AS_OF guard
  data/
    candidates.json     committed
    ground_truth.json   committed
    narration.json      committed
    headhunter.db       generated, git-ignored
  eval/
    jd/*.md             4 job descriptions
    jd/must_haves.json  machine-readable conditions
    expected/*.json     what judgement had to happen
    run_eval.py         --check and --score
    check_must_haves.py
    check_index.py      real FTS5, not the Python approximation
  artifacts/
    backend-rust/       one committed sample
```

There is no `db.rs`, `schema.rs`, or `tools.rs`. **No adapter code was needed** —
registering `sqlite` as a delegated executable puts it on the session's PATH, and
ailoy's existing `shell` tool already calls through `console.exec`.

The dataset generator lives in [`examples/_datagen`](../_datagen), which is deliberately
outside the cargo workspace — it is a Python tool, not a build target.

---

## 8. Known limits

**Plan B's recall figures are approximations, and one of them measures nothing.**
`variants.fts5_recall` never calls `sqlite3` and checks a single field. Run
`eval/check_index.py` for the real numbers: the skill and title axes gain 1-11 people
from the other four indexed fields, and the location axes turn out not to be search axes
at all.

**One style axis still separates the two populations.** Filtering to summaries of three
or more sentences reduces 600 to 191 while keeping 75% of the core — a lift of 2.4 over
random. The hand-written core tends toward three sentences and the generated background
toward two; the length targets used during generation do not constrain sentence count.

**The narration cannot be regenerated.** LLM output is not deterministic, so rerunning
produces different sentences. `narration.json` is a committed artifact; fixing one
person means deleting that id and regenerating it alone.

**The data is synthetic.** No relation to real people or companies; emails are
`example.com`. `validate.py` checks a denylist of real names.
