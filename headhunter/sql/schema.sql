-- LinkedIn Recruiter 제품 UI 가 리크루터에게 보여주는 것을 미러링한다(spec §2.0).
-- 어떤 LinkedIn API 도 아니다 — 프로스펙팅 검색 API 는 존재하지 않고, `openToWork` 는
-- 2020년에 생긴 UI 기능으로 어떤 공식 API 에도 필드로 노출된 적이 없다.
-- 각 컬럼 뒤 주석은 대응하는 Recruiter 검색 필터명이다.

CREATE TABLE candidates (
  id TEXT PRIMARY KEY,              -- urn:li:person:aBcD1234
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,          -- First names / Last names
  headline TEXT NOT NULL,           -- 함정 1(헤드라인 낚시)이 사는 곳
  summary TEXT NOT NULL,            -- 서술 계층이 채운다
  city TEXT NOT NULL,
  country TEXT NOT NULL,            -- Locations
  industry TEXT NOT NULL,           -- Industries
  job_function TEXT NOT NULL,       -- Job functions
  seniority TEXT NOT NULL,          -- Seniority. 함정 13 의 판정 근거
  profile_language TEXT NOT NULL,   -- Profile languages. 함정 10
  open_to_work INTEGER NOT NULL,    -- Open to work (Spotlight). 함정 7
  connections_count INTEGER NOT NULL,
  last_updated_at TEXT NOT NULL,    -- 함정 8(오래된 프로필)
  public_profile_url TEXT NOT NULL
);

CREATE TABLE positions (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  ord INTEGER NOT NULL,             -- JSON 배열 순서. 정답지의 descriptions 순서와 맞춘다
  title TEXT NOT NULL,              -- Job titles. current/past 구분은 end_year 로
  company_name TEXT NOT NULL,       -- 표기가 흔들린다(spec §3.4)
  company_urn TEXT NOT NULL,        -- 흔들려도 urn 은 같다
  company_size TEXT NOT NULL,       -- Company sizes. 함정 13 의 다른 축
  employment_type TEXT NOT NULL,    -- 함정 3(겸직)의 근거
  workplace_type TEXT NOT NULL,     -- 함정 6
  location TEXT NOT NULL,
  description TEXT NOT NULL,        -- 서술 계층이 채운다
  start_year INTEGER NOT NULL,
  start_month INTEGER NOT NULL,
  end_year INTEGER,
  end_month INTEGER,                -- NULL = 현직
  PRIMARY KEY (candidate_id, ord)
);

CREATE TABLE skills (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  name TEXT NOT NULL,
  endorsement_count INTEGER NOT NULL
);

CREATE TABLE educations (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  school_name TEXT NOT NULL,
  degree_name TEXT NOT NULL,
  field_of_study TEXT NOT NULL,
  start_year INTEGER NOT NULL,
  end_year INTEGER NOT NULL
);

CREATE TABLE certifications (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  name TEXT NOT NULL,
  authority TEXT NOT NULL
);

CREATE TABLE languages (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  name TEXT NOT NULL,
  proficiency TEXT NOT NULL         -- NATIVE_OR_BILINGUAL 등
);

-- `openToWork` 는 boolean 하나가 아니다. 구직자가 입력하고 리크루터에게만 보이는 하위
-- 필드가 있다(Recruiter 문서). 함정 7(open_to_work=false 인 강한 적합)을 다룰 때 의미를
-- 갖는 구조이므로 별도 테이블이다.
CREATE TABLE open_to_work_prefs (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  desired_title TEXT NOT NULL,      -- 최대 5개
  location_type TEXT NOT NULL,      -- On-site / Remote / Hybrid
  desired_location TEXT NOT NULL,
  start_date TEXT NOT NULL,
  employment_type TEXT NOT NULL
);

-- **있는 사람만 행을 갖는다.** 함정 12(연락처 없음)가 행의 부재로 표현된다.
CREATE TABLE contacts (
  candidate_id TEXT NOT NULL REFERENCES candidates(id),
  method TEXT NOT NULL,             -- inmail / referral
  note TEXT NOT NULL
);

CREATE INDEX positions_by_candidate ON positions(candidate_id);
CREATE INDEX skills_by_candidate ON skills(candidate_id);
CREATE INDEX skills_by_name ON skills(name);

-- 검색은 FTS5 다. 임베딩(`sqlite-vec`)을 쓰지 않는 이유는 spec §2.3 에 있다 — 실측으로
-- 커버리지와 순위가 FTS5 와 완전히 일치했고, 도메인 배선이 범용 도구 안으로 들어가
-- 층 분리를 깨뜨린다.
--
-- **`headline` 과 `skills` 를 둘 다 담아야 한다.** 계획 B 가 실측했다: 코어 65명 중
-- `rust` 토큰 보유자가 31명이고, 그중 29명은 두 표면에 중복으로 갖지만 2명은 한 곳에만
-- 갖는다 —
--
--   headline 만 : `headline-bait` 함정 (헤드라인에만 키워드가 있는 것이 그 함정의 정의)
--   skills 만   : `skills-without-evidence` 함정 (스킬 목록에만 있는 것이 정의)
--
-- 정의상 대체 표면이 없으므로 한쪽을 빼면 그 함정이 검색에 걸리지 않고, 검색 단계 함정이
-- 검색 결과에 없으면 함정이 아니다. 나머지 29명은 어느 쪽을 빼도 살아남으므로
-- **이 실패는 조용하다** — 데이터도 인덱스도 그럴듯하고 결과 크기도 정상이다.
--
-- 서술 계층이 채워진 뒤에도 유효하다. 다른 후보는 `description` 으로 표면이 하나 늘지만
-- 이 둘은 늘 수 없다 — `skills-without-evidence` 는 description 에 키워드가 **없는 것이**
-- 함정이고, `headline-bait` 는 headline 에만 있는 것이 함정이다.
CREATE VIRTUAL TABLE candidate_fts USING fts5(
  id UNINDEXED,
  headline,
  summary,
  titles,        -- 포지션 title 을 공백으로 이어붙인 것
  descriptions,  -- 포지션 description 을 이어붙인 것
  skill_names,   -- 스킬 이름을 이어붙인 것
  tokenize = 'unicode61'
);
