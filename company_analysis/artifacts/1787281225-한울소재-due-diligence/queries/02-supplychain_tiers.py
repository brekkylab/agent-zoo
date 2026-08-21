"""
공급망 tier 확장 (재귀, path 기반 visited guard).
CATALOG.md §2.3 지침: 방문 가드는 popping 이후 path 단위로 검사, 전역 visited 금지.
kr-hanul-materials 를 buyer 로 시작해 supplier 방향으로 재귀 확장.
"""
import csv
from collections import defaultdict

edges = []
with open('./data/supplychain/edges.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        edges.append(row)

sup_map = defaultdict(list)
for e in edges:
    sup_map[e['buyer_id']].append(e)

paths = []
def dfs(node, path, edge_path):
    for e in sup_map.get(node, []):
        nxt = e['supplier_id']
        if nxt in path:
            paths.append((edge_path + [e], 'CYCLE_STOP'))
            continue
        paths.append((edge_path + [e], 'OK'))
        dfs(nxt, path + [nxt], edge_path + [e])

dfs('kr-hanul-materials', ['kr-hanul-materials'], [])

for ep, status in paths:
    chain = ' -> '.join(['kr-hanul-materials'] + [e['supplier_id'] for e in ep])
    print(len(ep), status, chain, '| item:', ep[-1]['item'], 'confidence:', ep[-1]['confidence'])
