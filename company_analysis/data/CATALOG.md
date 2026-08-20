# Data Lake

**All of this data is synthetic.** No company, person, transaction, or sanctions entry
here exists. Only the schemas, types, and code systems follow the real thing
(OpenDART / SEC EDGAR / GLEIF). Reporting date `as_of = 2026-06-30`.
The lake is a fixed set of 12 companies — that set is the whole target, not a slice of a
larger one.

Read in this order: **this file → `registry/company_index.csv` → whichever source you need**

Korean account names, entity names, and codes appear verbatim in the data. They are
values to match on, not text to translate.

---

## 0. The first thing to know

**The three sources do not share a schema.** Nothing here is normalized into one shape.

| Source | Covers | Shape |
| --- | --- | --- |
| DART (Korea) | 5 domestic companies | Flat JSON, **every value is a STRING**, missing is `""` |
| EDGAR (US) | 1 US company | Nested JSON, numbers are numbers, `filings.recent` is **column-oriented parallel arrays** |
| GLEIF (global) | 11 companies | Normalized nested JSON, missing is `null` |

**Do not join on names.** The same company is spelled differently from file to file.
`company_id` in `registry/company_index.csv` is the only shared key.

---

## 1. Files

### registry/

| Path | Rows | What it is |
| --- | --- | --- |
| `company_index.csv` | 12 | `company_id, lei, corp_code, cik, primary_source, country`. **Every join starts here** |
| `dart_company/<corp_code>.json` | 5 | DART company profile. Domestic entities only |
| `dart_corpcode.xml` | 5 | DART entity-code list. Names differ from `dart_company` |
| `edgar_submissions/<cik>.json` | 1 | EDGAR filer information plus filing list |
| `gleif_lei.jsonl` | 11 | GLEIF LEI records. One line, one entity |
| `gleif_rr.jsonl` | 4 | GLEIF relationship records (consolidation). **No ownership percentage** |
| `ownership.csv` | 3 | `parent_id, child_id, share_pct, basis, gleif_rr, as_of, note` |

### financials/

| Path | What it is |
| --- | --- |
| `dart_fnltt/<corp_code>-<year>.json` | DART key accounts. **One file covers three fiscal years** (current, prior, prior-prior) |
| `edgar_facts/<cik>-<tag>.json` | EDGAR XBRL time series, one concept per file |

### the rest

| Path | Rows | What it is |
| --- | --- | --- |
| `supplychain/edges.csv` | 18 | `buyer_id ← supplier_id`. **No tier column** — tiers are what a recursive join produces |
| `risk/sanctions.csv` | 7 | OFAC SDN shape. **No `company_id` mapping** — name matching is on you |
| `reference/industry_xwalk.csv` | 7 | KSIC ↔ SIC ↔ NAICS. **Not one-to-one** |
| `reference/fx_rates.csv` | 23 | Monthly rates against KRW |
| `watchlist.csv` | 6 | Monitoring targets |

---

## 2. Joins

### 2.1 The basics: `company_id`, never a name

```sql
-- sources only connect through company_index
SELECT i.company_id, i.country, i.primary_source
FROM read_csv_auto('data/registry/company_index.csv') i
WHERE i.corp_code <> ''            -- domestic entities only
```

### 2.2 DART ↔ GLEIF joins on the business registration number

**The hyphenation differs.** Without normalizing it you get zero rows.

```
DART   bizr_no       "9991001234"
GLEIF  registeredAs  "999-10-01234"
```

```sql
SELECT d.corp_name, g.entity.legalName.name
FROM read_json_auto('data/registry/dart_company/*.json') d
JOIN read_json_auto('data/registry/gleif_lei.jsonl') g
  ON d.bizr_no = replace(g.entity.registeredAs, '-', '')
```

Joining on the English name fails; the spellings differ subtly.

### 2.3 Expanding the supply chain by tier: a visit guard is mandatory

**This graph contains cycles.** Recursing without a guard does not terminate.

The guard asks whether the node is **already on the path travelled so far**, not
whether it is already queued. Check it after popping, not before pushing. A depth
limit alone will not stop it: going around a cycle lowers the recorded depth again,
so the cutoff never fires.

- **SQL** (`WITH RECURSIVE`): accumulate the visited nodes into an array and refuse to
  extend when the next node is already in it.
- **Python**: carry a path set along on the stack or queue and skip a node that is
  already in it. A single global `visited` also erases nodes that legitimately
  reappear on a different path.

Because the guard is per-path, the same company shows up on more than one path. That
is expected; decide what counts as one occurrence and state that basis in the report.

### 2.4 Sanctions matching: name similarity is all you have

`sanctions.csv` has no `company_id`. You have to match on names and aliases, and
**the spellings do not line up exactly.** Proposing candidates is the right answer;
asserting a match is the wrong one.

```sql
-- the aliases column is semicolon-separated, multi-valued
SELECT s.entity_name, s.aliases, s.program, s.listed_on
FROM read_csv_auto('data/risk/sanctions.csv') s
```

Look at indirect exposure too: a supplier can be clean itself while its parent in
`ownership.csv` is on the list.

---

## 3. Common mistakes

### 3.1 Not re-applying the `fs_div` filter to the response (the most dangerous one)

A single `dart_fnltt/*.json` file holds **both consolidated (CFS) and separate (OFS)
statements.** The same `account_nm` carries two values. Without filtering, the figures
get mixed together.

An invented example, to show the shape:

```
(주)가온소재 FY20XX 매출액
  CFS (consolidated)   251,904,338,000
  OFS (separate)       187,332,110,000    ← the gap between the two can be large
```

A report **must say which basis it used.**

### 3.2 Grouping by `account_nm` and double-counting

The same `account_nm` sometimes appears **more than once** in one response, with the
same value. Summing it as-is double-counts, so distinguish by `ord` or dedupe.
`ord` is not contiguous.

### 3.3 Amounts are strings, not numbers

```
"251,904,338,000"     comma-separated
"-8,415,720,000"      negatives take a leading '-', not parentheses
""                    missing
```

**The unit is won, unscaled.** Not millions, not thousands. EDGAR's
`units.USD[].val` is the opposite: a number, in dollars. Do not compare the two
directly.

### 3.4 Querying a financial-sector entity with manufacturing accounts

There is a financial-sector entity in the set. Its statements have **neither `매출액`
(revenue) nor `영업이익` (operating profit).** They use accounts like `순이자손익`
(net interest income), `이자수익`, `이자비용`, `순수수료손익`, and `예수부채`
(deposits), and operating profit is spelled `영업이익(손실)`, **a different string.**
Looking for manufacturing account names returns nothing.

### 3.5 Reading `share_pct` from the supplier's side

`share_pct` in `edges.csv` is **the buyer's share of procurement.** It is not the
supplier's share of revenue.

### 3.6 Deciding listed status from `stock_code`

A missing `stock_code` in `dart_corpcode.xml` is not an empty string but **a single
space.** `if stock_code:` marks every unlisted company as listed. In
`dart_company/*.json` it is an empty string. **It differs per file.**

### 3.7 Not reconciling `induty_code` length

KSIC codes are **mixed 3-digit and 5-digit** (`102` vs `10211`). Joining them as-is
does not match. The mapping in `industry_xwalk.csv` is not one-to-one either: one
KSIC can carry several SICs. And an industry code sometimes disagrees with what the
company actually does.
