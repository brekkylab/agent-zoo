import csv, json, difflib

sanctions = list(csv.DictReader(open('./data/risk/sanctions.csv')))
gleif = [json.loads(l) for l in open('./data/registry/gleif_lei.jsonl')]
idx = list(csv.DictReader(open('./data/registry/company_index.csv')))

# candidate company names (english + native) from gleif + company_index
companies = {}
for g in gleif:
    lei = g['lei']
    names = [g['entity']['legalName']['name']]
    for o in g['entity'].get('otherNames', []):
        names.append(o['name'])
    companies[lei] = names

id_by_lei = {c['lei']: c['company_id'] for c in idx if c['lei']}

def norm(s):
    return s.upper().replace(',', '').replace('.', '').replace('(주)', '').replace('CO LTD', '').replace('LTD', '').replace('INC', '').strip()

results = []
for s in sanctions:
    names_to_check = [s['entity_name']] + s['aliases'].split(';')
    for lei, names in companies.items():
        cid = id_by_lei.get(lei, '(no company_id/domestic KR entity)')
        for cname in names:
            for sname in names_to_check:
                ratio = difflib.SequenceMatcher(None, norm(cname), norm(sname)).ratio()
                if ratio > 0.55:
                    results.append({
                        'sanctions_entity': s['entity_name'],
                        'sanctions_list': s['list_name'],
                        'program': s['program'],
                        'listed_on': s['listed_on'],
                        'matched_alias': sname,
                        'company_id': cid,
                        'company_name': cname,
                        'ratio': round(ratio, 3),
                    })

results.sort(key=lambda r: -r['ratio'])
for r in results:
    print(r)

json.dump(results, open('./workspace/1787282199-한울소재-supply-chain-risk/sanctions_candidates.json', 'w'), ensure_ascii=False, indent=2)
