# Headhunter 예제

인재풀 데이터베이스를 환경으로 갖는 헤드헌팅 에이전트.

채용공고(JD)를 주면 에이전트가 600명 인재풀을 검색해 상위 *k*명을 고르고, 각자에게
보낼 개인화된 콜드메일 초안을 `artifacts/` 아래에 쓴다.

```
jd.md ──▶ [ headhunter agent ] ──▶ artifacts/<role-slug>/00-shortlist.md
              │                    artifacts/<role-slug>/01-<candidate>.md
              │                    artifacts/<role-slug>/02-<candidate>.md
              ▼                    ...
   data/headhunter.db (600명)
```

에이전트가 쥐는 도구는 **하나**다 — 읽기 전용 SQL 을 돌리는 `sqlite`. 사람 목록을
받는 것이 아니라 직접 쿼리를 짜서 좁혀 나간다.

[SCENARIO.md](SCENARIO.md) 가 이 예제가 무엇을 보여주는지, [TRANSCRIPT.md](TRANSCRIPT.md)
가 실행 화면을 담고 있다.

---

## 1. 실행

**두 레포가 형제로 있어야 한다.** `Cargo.toml` 의 경로 의존이 `../../../cortex/` 를
가리킨다 — cortex 가 아직 배포되지 않고 ailoy 와 나란히 개발되기 때문이다.

```
~/workspace/
  ailoy/
  cortex/
```

```bash
# 1. 인증. 기본 프로바이더가 Bedrock 이다.
#    저장소 루트 `.env` 에 넣으면 된다 — 바이너리가 읽고, `dotenv()` 가 위로 올라가며
#    찾으므로 어느 디렉터리에서 돌려도 같은 파일을 집는다.
cat > .env <<'ENV'
AWS_BEARER_TOKEN_BEDROCK=...
AWS_REGION=ap-northeast-2
ENV

# 2. cortex 체크아웃에서 콘솔 서버를 빌드한다
cd ../cortex && cargo build -p cortex-local-console
export AILOY_CORTEX_CONSOLE=$PWD/target/debug/cortex-local-console

# 3. 커밋된 JSON 에서 DB 를 만든다
cd ../ailoy/examples/_datagen
python3.11 -m venv .venv && .venv/bin/pip install -q pytest
cd ../headhunter        # 이후 명령은 전부 여기서 돈다
../_datagen/.venv/bin/python sql/load.py

# 4. 실행 — 저장소 루트가 아니라 `examples/headhunter` 에서
cargo run -p headhunter -- --jd eval/jd/backend-rust.md --k 3
```

**작업 디렉터리가 중요하다.** `main.rs` 가 현재 디렉터리를 에이전트의 트리로 마운트하고,
지침은 DB 를 `data/headhunter.db` 라는 **워크스페이스 상대 경로**로 부른다. 저장소
루트에서 돌리면 에이전트의 첫 쿼리부터 `no database at data/headhunter.db` 를 받고,
산출물도 `run_eval.py --score` 가 보는 자리가 아닌 곳으로 나간다.

`AWS_REGION` 이 없으면 `AWS_DEFAULT_REGION`, 그것도 없으면 `us-east-1` 이다. 키가
설정됐지만 **비어 있으면 프로바이더를 아예 등록하지 않는다** — 호출 시점의 401 대신
"no provider found" 로 실패한다.

다른 프로바이더도 그대로 쓴다 — `--model anthropic/claude-sonnet-5` 이면
`ANTHROPIC_API_KEY` 를 읽는다. Bedrock 쪽 모델 이름은 **inference-profile id** 여야
하고 맨 foundation-model id 는 on-demand throughput 에서 거부된다. Bedrock 은 SSE
리더가 못 읽는 바이너리 이벤트 스트림을 쓰지만, 이 예제는 `stream: false` 로 보내는
`agent.run()` 을 소비하므로 그 제약이 여기엔 적용되지 않는다.

`data/headhunter.db` 는 생성물이고 gitignore 대상이다. 원본 JSON 이 커밋돼 있으므로
언제든 다시 만들 수 있다.

| 플래그 | 기본값 | |
| --- | --- | --- |
| `--jd` | `jd.md` | 읽을 채용공고 |
| `--k` | `3` | 숏리스트 인원. 적격자가 적으면 적게 내고 이유를 쓴다 |
| `--out` | `artifacts` | 산출물 루트. 그 아래 `<role-slug>/` 를 만든다 |
| `--model` | `bedrock/global.anthropic.claude-sonnet-5` | `<provider>/<model>`. Bedrock 은 inference-profile id 를 요구한다 |
| `--console` | `cortex-local-console` | `AILOY_CORTEX_CONSOLE` 로도 받는다 |

---

## 2. 인재풀이 어려운 이유

600명은 무작위가 아니다. **65명이 손으로 설계**됐고 그중 17명이 함정이다 — 쿼리로는
통과하지만 사람이 읽으면 틀린 사람들.

| 함정 | 어떻게 생겼나 | 왜 어려운가 |
| --- | --- | --- |
| `headline-bait` | headline 에 `learning Rust` | `MATCH 'rust'` 에 걸린다. 스킬 목록엔 없다 |
| `overlapping-tenure` | 두 직장이 24개월 겹침 | 문장에 그런 말이 없고, 4년 임계에 정확히 걸친다 |
| `stale-profile` | 2024-03 이후 갱신 없음 | 현직을 믿으면 경력이 29개월 늘어난다 |
| `inflated-title` | 10명 회사의 CXO | 직함만 보면 인재풀 최상위다 |
| `duplicate-profile` | 한 사람의 두 계정 | 상위 *k* 에 둘 다 있으면 실패 |
| `same-name` | 같은 이름의 두 사람 | 합치면 실패 — 반대 방향 시험이다 |

함정마다 **대조군**이 있다. 정확히 한 축만 다르고 그 축이 통과하는 쪽이다.
`headline-bait` 옆에는 헤드라인이 거의 같지만 Rust 실무 경험이 실제로 있는 사람이
있다. 둘을 가르려면 프로필을 읽어야 한다 — "수상해 보이는 쪽을 버리는" 방법은 대조군도
같이 버리고, **그것이 정답과 "이유가 틀린 정답"을 가르는 지점**이다.

---

## 3. 데이터

세 파일이 id 로만 이어진다.

| 파일 | | |
| --- | --- | --- |
| `data/candidates.json` | 884 KB | 사실 — 이름·회사·기간·스킬·연락처 |
| `data/ground_truth.json` | 300 KB | JD 무관 라벨. `data/` **밖**에서 읽는다 |
| `data/narration.json` | 533 KB | 요약 600 · 포지션 설명 1,006 |

서술을 별도 파일에 둔 이유가 둘이다. `gen.py` 가 `candidates.json` 을 덮어쓰므로 거기
넣으면 `make gen` 한 번이 LLM 산출물을 지우고, **LLM 출력은 비결정적이라 되돌릴 수
없다.** 그리고 문장이 잘못된 사람을 찾으면 **그 id 만** 다시 만들 수 있다.

### 3.1 스키마

**LinkedIn Recruiter** — 리크루터가 실제로 쓰는 유료 제품 — 이 검색 필터와 프로필
화면에 보여주는 것을 미러링한다. 어떤 LinkedIn API 도 아니다: 프로스펙팅 검색 API 는
존재하지 않고 `openToWork` 는 어떤 공식 API 에도 노출된 적이 없다. 값 목록(직급 단계,
회사 규모 구간)은 제품이 제공하는 것을 단순화했다.

테이블 8개: `candidates`, `positions`, `skills`, `educations`, `certifications`,
`languages`, `open_to_work_prefs`, `contacts`.

두 관례가 의미를 갖는다:

- `contacts` 는 **연락할 수 있는 사람만** 행을 갖는다. 행이 없으면 연락 수단이 없다는
  뜻이고, 그것이 `no-contact` 함정이다 — null 이 아니라 부재로 표현된다.
- `positions` 에서 `end_year IS NULL` 이 현직이다. 별도 boolean 이 없으므로 관례가
  한 곳에만 산다.

**파생값을 저장하지 않는다.** 총 경력 개월, 현재 직장, 현재 직함 — 전부 없고
`positions` 에서 계산한다. 저장하면 함정 두 개가 동시에 사라진다.

### 3.2 VIEW — 도메인 계층

도메인 지식이 여기 있다(spec §1.1). `sqlite` 실행파일이 아니라 — 그쪽은 범용 도구로
남는다.

| VIEW | |
| --- | --- |
| `candidate_tenure` | `naive_months` 와 `real_months`. 뒤쪽이 겸직 중첩을 걷어낸 값 |
| `current_position` | 후보당 한 행 — 가장 최근 시작한 현직 |
| `candidate_brief` | 좁은 스캔 VIEW. 여기서 시작한다 |
| `skill_distribution`, `title_distribution`, `location_distribution` | 데이터의 지형 |

`candidate_tenure` 는 26줄짜리 gaps-and-islands SQL 이다. 어려움을 없애는 것이 아니라
**옮긴다** — 포지션 기간을 직접 더하는 에이전트는 여전히 틀리고, 그것이
`overlapping-tenure` 함정이다.

`candidate_brief` 는 컨텍스트 예산 때문에 있다. `sqlite` 도구는 행 상한만 있고 바이트
상한이 없어서 `SELECT * FROM candidates LIMIT 100` 이 긴 요약 100개를 컨텍스트에
붓는다. 좁은 VIEW 와 "`SELECT *` 금지" 지침이 층 분리의 답이다 — 도구에 바이트 상한을
넣으면 두 번째 절단 축과 그것을 알리는 두 번째 표기가 생긴다.

### 3.3 검색은 FTS5

`candidate_fts` 가 headline·summary·titles·descriptions·skill_names 를 색인한다.
`headline` 과 `skill_names` **둘 다** 하중을 받는다: 함정 둘이 각각 한 표면에만 살아서,
어느 한 컬럼을 빼면 그 함정이 검색 결과에서 사라진다.

**임베딩이 아니다.** cortex 에 `sqlite-vec` 가 있고 이 데이터로 FTS5 와 비교 측정했다 —
커버리지와 순위가 완전히 일치했다. 갈리는 것은 도메인 배선이 어디 앉느냐다. 임베딩
검색은 그것을 범용 도구 안으로 밀어넣어 이 예제의 주제인 층 분리를 깨뜨린다.

어휘는 일부러 흔들려 있다 — `Rust` 가 `rust-lang`·`Rust Lang`·`Async Rust`·`Tokio`·
`러스트` 로 나타난다. `MATCH 'rust'` 하나가 보유자의 85~95% 를 찾으므로, 에이전트가
지형을 먼저 보고 쿼리를 넓히라고 분포 VIEW 가 있다.

**지역은 색인에 없다.** `MATCH 'seoul'` 은 426명이 아니라 **1명**을 데려온다 — 색인은
자유 텍스트를 담고 지역은 정확한 컬럼이 있으므로 `WHERE city IN (...)` 이 더 정확하고,
실은 그것만 동작한다. 계획 B 의 생성기가 `Seoul, KR`·`Tokyo, JP` 의 "재현율" 을 재긴
했는데, 그 수는 `positions.location` 문자열에 그 토큰이 있는 비율이었고 검색이
아니었다. `eval/check_index.py` 가 두 종류의 축을 구별하는 이유다.

---

## 4. 에이전트

지침은 [`src/prompt.rs`](src/prompt.rs) 에 있다. 스키마·VIEW 목록·루프, 그리고
`sqlite` 도구의 `--help` 가 말하지 않는 동작 넷을 담는다 — SQL 안의 `LIMIT` 이 절단
안내를 침묵시킨다는 것도 그중 하나이고, 그래서 에이전트가 20행을 전부라고 믿게 된다.

### 4.1 루프

1. JD 를 읽고 요구사항을 구조화한다
2. 분포 VIEW 로 인재풀의 표기를 본다
3. 여러 번 검색한다 — 직함으로, 스킬로, 인접 스킬로. 한 쿼리가 아니다
4. 유망한 후보의 전체 프로필을 읽고 **서로 비교하며** 평가한다
5. 상위 *k* 를 고른다. 적격자가 적으면 적게 내고 이유를 쓴다
6. 숏리스트와 선정자마다 콜드메일 하나를 쓴다

3단계가 내려놓는 집합이 기본 JD 기준 **40~70명**이다 — `MATCH 'rust'` 에 실경력 4년을 걸면 실측 63명이다. 4단계가 정독해야 하는 크기이고,
그것이 이 수를 정한다.

### 4.2 왜 서브에이전트가 아니라 메인 루프인가

후보마다 서브에이전트를 띄우면 컨텍스트를 아낀다. 그렇게 하지 않았고, 이유는 4단계의
**비교**라는 단어에 있다.

두 기록이 한 사람일 수 있고, 두 사람의 순서가 합산 방식에 따라 뒤집힐 수 있다. 어느
쪽도 프로필 하나 안에서는 보이지 않는다. 격리된 서브에이전트는 그 비교를 할 수 없고,
그러면 **데이터셋이 시험하려는 것 자체가 시험되지 않는다.**

### 4.3 랭킹 요구사항

- 후보마다 프로필에 있는 사실만 인용한 근거를 붙인다
- 위험도 기록한다 — 지역 불일치, 얇은 경력, 다른 도메인, 오래된 프로필
- must-have 를 명백히 못 넘긴 사람은 상위 *k* 에 들어가지 않는다
- **버린 사람과 이유를 적는다.** 없으면 나중에 검증할 수 없다. `<!-- rejected -->` 가
  거절 구역의 시작을 표시해 채점기가 선정과 거절을 구별한다
- 콜드메일은 후보의 `profile_language` 로 쓴다
- 후보·회사·날짜·스킬을 지어내지 않는다

---

## 5. 산출물

```
artifacts/backend-rust/
  00-shortlist.md         고른 사람과 버린 사람, 둘 다 이유와 함께
  01-chaewon-noh.md       선정자마다 콜드메일 하나
  02-haeun-seong.md
  03-nova-vance.md
```

샘플 한 벌이 `artifacts/backend-rust/` 에 커밋돼 있다. 이후 실행은 그 옆에 쓰이고
gitignore 된다 — 형태를 보여주는 데는 한 벌이면 충분하고, 매 실행을 커밋하면 그 한
벌이 묻힌다.

콜드메일은 **InMail 초안**으로 쓴다. 인재풀에 이메일 주소가 없고 그것이 정확하다 —
LinkedIn 은 이메일을 노출하지 않으며, 있다고 가정한 초안은 틀린 것을 가르친다.

---

## 6. 채점

정답지는 **랭킹이 아니라 사실**이다. "채원 노가 1위" 는 특정 JD 를 전제하므로 다른
JD 에서는 아무것도 말해주지 않는다. "예준 노의 실경력은 180개월이고 순진한 합산은
308개월" 은 JD 와 무관하게 성립한다 — 25년이라고 말하는 에이전트는 무엇을 물었든
틀렸다.

```bash
# 에이전트를 돌리기 전: 채점 기준이 데이터와 맞는가
../_datagen/.venv/bin/python eval/run_eval.py --check

# 돌린 뒤: 산출물 채점
../_datagen/.venv/bin/python eval/run_eval.py --score artifacts/backend-rust
```

`--check` 는 각 JD 의 적격자 수가 `must_haves.json` 이 말하는 값과 같은지, 그리고
`eval/expected/` 의 모든 id 가 실재하는 사람인지 본다. 손으로 적은 수는 데이터가
바뀌면 썩고, 틀린 id 는 **fail-open** 이다 — 존재하지 않는 사람에 대한
`must_not_appear` 는 에이전트가 무엇을 하든 통과한다.

`--score` 는 자동 실패와 사람이 읽어야 할 것을 나눈다. 완전 자동 채점은 목표가
아니다(spec §6.2) — 개인화 문장이 자연스러운지, 거절 사유가 정보를 주는지는 읽어야
안다.

네 JD 가 서로 다른 것을 시험한다:

| JD | 적격 / k | 시험 대상 |
| --- | --- | --- |
| `backend-rust` | 56 / 3 | 좁히기 |
| `ml-platform-tokyo` | 9 / 12 | 적게 내고 이유 쓰기 |
| `backend-seoul-ko` | 28 / 3 | 후보의 언어로 쓰기 |
| `blockchain-solidity` | 0 / 5 | 아무도 없다고 말하기 |

마지막이 가장 중요하다. 인재풀에 Solidity 를 아는 사람이 없고, 근접 오답 5명이 심어져
있다 — `on-chain analytics`, `web3 curious`. 이것이 없으면 데이터셋이 "항상 답이 있다"
는 것을 가르치는데, 실무에서 그것이 가장 비싼 오답이다.

`ml-platform-tokyo` 는 적격자를 1명으로 줄일 수 없다. spec §4.1 이 1명이라고 적었지만
9명 중 3명이 대조군이고 **대조군은 정의상 적격자다** — 걸러내면 에이전트가 함정과
대조군을 함께 버려 아무것도 시험되지 않는다. 대신 `k` 를 올렸고, 같은 행동이 시험된다.

---

## 7. 레이아웃

```
examples/headhunter/
  Cargo.toml            ../../../cortex/ 경로 의존
  src/
    main.rs             CLI · 콘솔 조립 · 스트림 소비
    prompt.rs           지침
  sql/
    schema.sql          테이블 8개 + candidate_fts
    views.sql           도메인 계층
    load.py             JSON → SQLite, AS_OF 가드 포함
  data/
    candidates.json     커밋됨
    ground_truth.json   커밋됨
    narration.json      커밋됨
    headhunter.db       생성물, gitignore
  eval/
    jd/*.md             채용공고 4종
    jd/must_haves.json  기계 판독 가능한 조건
    expected/*.json     어떤 판단이 있었어야 하는가
    run_eval.py         --check 와 --score
    check_must_haves.py
    check_index.py      파이썬 근사치가 아니라 진짜 FTS5
  artifacts/
    backend-rust/       커밋된 샘플 한 벌
```

`db.rs`·`schema.rs`·`tools.rs` 는 없다. **어댑터 코드가 필요 없었다** — `sqlite` 를
delegated executable 로 등록하면 세션의 PATH 에 올라가고, ailoy 의 기존 `shell` 툴이
이미 `console.exec` 로 그것을 부른다.

데이터셋 생성기는 [`examples/_datagen`](../_datagen) 에 있고 **일부러 cargo 워크스페이스
밖**이다 — 파이썬 도구이고 빌드 대상이 아니다.

---

## 8. 알려진 한계

**계획 B 의 재현율은 근사치이고, 그중 하나는 아무것도 재지 않는다.**
`variants.fts5_recall` 은 `sqlite3` 를 부르지 않고 한 필드만 본다. 실제 값은
`eval/check_index.py` 가 낸다 — 스킬·직함 축은 나머지 네 필드에서 1~11명이 추가되고,
지역 축은 애초에 검색 축이 아니었다는 것이 드러난다.

**문체 축 하나가 두 집단을 아직 가른다.** 요약이 3문장 이상인 사람으로 좁히면 600명이
191명이 되고 코어의 75% 가 남는다 — 무작위 대비 2.4배. 손으로 쓴 코어는 3문장, 생성된
배경은 2문장 쪽으로 기운다. 생성 때 쓴 길이 목표가 문장 수를 구속하지 않는다.

**서술은 재생성할 수 없다.** LLM 출력은 비결정적이라 다시 돌리면 다른 문장이 나온다.
`narration.json` 은 커밋된 산출물이고, 한 사람을 고치려면 그 id 만 지우고 다시 만든다.

**데이터는 합성이다.** 실존 인물·회사와 무관하며 이메일은 `example.com` 이다.
`validate.py` 가 실존 인명 denylist 를 대조한다.
