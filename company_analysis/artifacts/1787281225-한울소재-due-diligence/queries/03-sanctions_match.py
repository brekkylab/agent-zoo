"""
제재 명단(sanctions.csv, 7건) 대 GLEIF 11개사 이름/별칭 유사도 매칭.
company_id 매핑은 company_index.csv 의 lei 컬럼을 통해 확인.
CATALOG.md §2.4 지침: 이름 매칭만 가능, "가능성 있는 일치"까지만 제시.
"""
import csv, json, difflib

sanctions = []
with open('./data/risk/sanctions.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        sanctions.append(row)

companies = {}
with open('./data/registry/gleif_lei.jsonl') as f:
    for line in f:
        d = json.loads(line)
        companies[d['lei']] = {
            'ko': d['entity']['legalName']['name'],
            'en': [n['name'] for n in d['entity'].get('otherNames', [])]
        }

idx = {}
with open('./data/registry/company_index.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        if row['lei']:
            idx[row['lei']] = row['company_id']

def norm(s):
    return s.upper().replace(',', '').replace('.', '').replace('(주)', '').strip()

results = []
for lei, info in companies.items():
    cid = idx.get(lei, '?')
    cand_names = [norm(info['ko'])] + [norm(n) for n in info['en']]
    for s in sanctions:
        sanc_names = [norm(s['entity_name'])] + [norm(a) for a in s['aliases'].split(';')]
        best = 0
        for cn in cand_names:
            for sn in sanc_names:
                ratio = difflib.SequenceMatcher(None, cn, sn).ratio()
                best = max(best, ratio)
        if best > 0.55:
            results.append((best, cid, info, s['entity_name'], s['program'], s['listed_on']))

for r in sorted(results, reverse=True):
    print(f"{r[0]:.2f} | {r[1]} <-> {r[3]} ({r[4]}, listed {r[5]})")
