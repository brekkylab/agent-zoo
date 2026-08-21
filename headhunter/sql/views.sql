-- 도메인 지식은 여기 있다(spec §1.1). 겸직 기간 중첩을 걷어내는 이 26줄은 채용 도메인의
-- 판단이지 DB 기능이 아니므로 `cortex-execs/sqlite` 가 아니라 예제의 VIEW 에 있다.
-- 에이전트는 `SELECT * FROM candidate_tenure WHERE real_years >= 4` 만 쓴다.
--
-- 어려움이 사라지는 것이 아니라 옮겨간다. VIEW 를 쓰지 않고 단순 합산하면 여전히 틀린다 —
-- 그것이 함정 3 이다.
--
-- CTE 를 네 단계로 나눈 것은 SQLite 가 윈도우 함수를 집계 안에 중첩하는 것을 거부하기
-- 때문이다(`misuse of window function MAX()`). 이런 비자명한 제약을 에이전트가 매 턴
-- 겪지 않게 하는 것이 VIEW 를 두는 이유이기도 하다.
--
-- `2026*12+8` 은 생성기 `_datagen/common/dates.py` 의 `AS_OF` 와 같아야 한다.
-- `load.py` 의 `assert_as_of_matches` 가 검사한다 — 어긋나면 조용히 틀린다.
CREATE VIEW candidate_tenure AS
WITH span AS (
  SELECT candidate_id AS id,
         start_year*12 + COALESCE(start_month,1) AS s,
         COALESCE(end_year*12 + COALESCE(end_month,1), 2026*12+8) AS e
  FROM positions
),
scan AS (
  SELECT id, s, e,
         MAX(e) OVER (PARTITION BY id ORDER BY s
                      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_end
  FROM span
),
island AS (
  SELECT id, s, e,
         SUM(CASE WHEN prev_end IS NULL OR s > prev_end THEN 1 ELSE 0 END)
           OVER (PARTITION BY id ORDER BY s) AS grp
  FROM scan
),
merged AS (SELECT id, grp, MIN(s) AS s, MAX(e) AS e FROM island GROUP BY id, grp)
SELECT c.id, c.first_name || ' ' || c.last_name AS name,
       (SELECT SUM(e-s) FROM span WHERE span.id = c.id) AS naive_months,
       SUM(m.e - m.s) AS real_months,
       ROUND(SUM(m.e - m.s)/12.0, 1) AS real_years
FROM merged m JOIN candidates c ON c.id = m.id
GROUP BY c.id, name;

-- `end_year IS NULL` 이 현직이라는 관례를 한 곳에 가둔다. 별도 boolean 을 두지 않은
-- 것은 README 원안을 따른 것이며(spec §2.0), 값이 하나뿐이라 관리 지점이 적다.
--
-- **후보당 한 행이어야 한다.** 현직이 둘 이상인 사람이 실측 17명 있다 — 겸직이고,
-- 그것이 함정 3 의 재료다. 이 VIEW 를 `candidate_brief` 가 `LEFT JOIN` 하므로 여러
-- 행을 내보내면 스캔 목록에서 그 17명이 두 번 나온다. 실제로 그랬다: 600명 DB 인데
-- `candidate_brief` 가 617행이었다.
--
-- 조용한 실패다. 목록은 그럴듯하고, 세면 인원이 부풀고, `--limit 50` 을 걸면 한 명이
-- 말없이 밀려난다. 그리고 밀려나는 쪽이 하필 겸직자 — 즉 함정 계열이다.
--
-- 가장 최근에 시작한 것을 대표로 삼는다. 겸직 사실 자체는 `candidate_tenure` 의
-- `naive_months` vs `real_months` 차이로 남아 있고, 이 VIEW 가 답하는 질문은
-- "지금 어디 다니는가" 하나다.
CREATE VIEW current_position AS
SELECT p.candidate_id AS id, p.title, p.company_name, p.company_size,
       p.employment_type, p.workplace_type, p.location,
       p.start_year, p.start_month
FROM positions p
WHERE p.end_year IS NULL
  AND p.ord = (SELECT q.ord FROM positions q
               WHERE q.candidate_id = p.candidate_id AND q.end_year IS NULL
               ORDER BY q.start_year DESC, q.start_month DESC, q.ord
               LIMIT 1);

-- 앞의 둘은 계산을 대신하고, 이 셋은 데이터의 지형을 보여준다(spec §2.2).
--
-- 왜 필요한가: 표기가 흔들려 있다(spec §3.4). `Rust` 가 `rust-lang`·`Rust Lang`·
-- `Async Rust`·`Tokio`·`러스트` 로 나타나고, FTS5 의 `MATCH 'rust'` 재현율이 85~95% 다 —
-- 즉 5~15% 는 못 찾는다. 에이전트가 이 VIEW 로 지형을 먼저 보고 쿼리를 넓히는 행동이
-- DATASET_PLAN §2.2 가 요구하는 바다.
CREATE VIEW skill_distribution AS
SELECT name, COUNT(*) AS holders
FROM skills GROUP BY name ORDER BY holders DESC;

CREATE VIEW title_distribution AS
SELECT title, COUNT(*) AS holders
FROM positions GROUP BY title ORDER BY holders DESC;

CREATE VIEW location_distribution AS
SELECT location, COUNT(*) AS positions_here
FROM positions GROUP BY location ORDER BY positions_here DESC;

-- **좁은 VIEW 다. 에이전트의 1차 스캔이 이것을 쓴다.**
--
-- `sqlite` 도구는 행 상한(`--limit`)만 있고 바이트 상한이 없다(계획 A). 그래서
-- `SELECT * FROM candidates LIMIT 100` 은 긴 `summary` 100개를 컨텍스트에 붓는다 —
-- 수십에서 수백 KB 다. 층 분리(spec §1.1)가 이미 답을 갖고 있다: 도메인 층이 좁은 VIEW 를
-- 주고 지침이 `SELECT *` 를 금한다.
--
-- 도구에 바이트 상한을 넣는 것은 명백한 개선이 아니다 — 두 번째 절단 축과 그것을 알리는
-- 두 번째 표기가 생긴다.
--
-- `summary` 와 `description` 이 없는 것이 이 VIEW 의 요점이다. 그것을 읽는 것은 2차
-- 정독(spec §5.3 의 4단계)이고, 그때는 한 사람씩 본다.
--
-- `contact_rows` 가 0 이면 연락할 수단이 없다 — 함정 12 다. `LEFT JOIN` 인 이유는
-- 현직이 없는 사람(전원 종료된 포지션)이 있기 때문이며, 그때 `current_title` 이 NULL 이 된다.
CREATE VIEW candidate_brief AS
SELECT c.id, c.first_name || ' ' || c.last_name AS name,
       c.headline, c.city, c.country, c.seniority, c.job_function,
       c.profile_language, c.open_to_work, c.last_updated_at,
       t.real_years,
       cp.title AS current_title, cp.company_name AS current_company,
       cp.company_size AS current_company_size,
       (SELECT COUNT(*) FROM contacts x WHERE x.candidate_id = c.id) AS contact_rows
FROM candidates c
LEFT JOIN candidate_tenure t ON t.id = c.id
LEFT JOIN current_position cp ON cp.id = c.id;
