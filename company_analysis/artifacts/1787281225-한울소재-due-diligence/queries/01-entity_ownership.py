"""
실체 확인 & 지분구조 조회.
- data/registry/company_index.csv 에서 kr-hanul-materials 행 확인
- data/registry/dart_company/99000101.json 프로필
- data/registry/gleif_lei.jsonl 에서 HANUL LEI 레코드 (bizr_no vs registeredAs 하이픈 제거 비교)
- data/registry/ownership.csv 에서 parent_id 또는 child_id == kr-hanul-materials 인 행
- data/registry/gleif_rr.jsonl 교차검증
"""
import json, csv

with open('./data/registry/dart_company/99000101.json') as f:
    dart = json.load(f)
print('DART:', dart['corp_name'], dart['bizr_no'], dart['ceo_nm'], dart['est_dt'])

with open('./data/registry/gleif_lei.jsonl') as f:
    for line in f:
        d = json.loads(line)
        if d['lei'] == '0000HANULMAT00001A90':
            reg = d['entity']['registeredAs'].replace('-', '')
            print('GLEIF registeredAs (normalized):', reg, '== bizr_no?', reg == dart['bizr_no'])

with open('./data/registry/ownership.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        if row['parent_id'] == 'kr-hanul-materials' or row['child_id'] == 'kr-hanul-materials':
            print('OWNERSHIP:', row)
