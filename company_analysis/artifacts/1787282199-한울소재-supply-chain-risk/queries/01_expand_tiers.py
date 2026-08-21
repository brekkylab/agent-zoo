import csv, json
from collections import defaultdict

edges = list(csv.DictReader(open('./data/supplychain/edges.csv')))

# build buyer -> [supplier edges]
by_buyer = defaultdict(list)
for e in edges:
    e['share_pct'] = float(e['share_pct'])
    by_buyer[e['buyer_id']].append(e)

ROOT = 'kr-hanul-materials'

# DFS with per-path visited guard; check guard AFTER popping (i.e., don't extend if next node already in path)
paths = []  # each: list of edges from root to leaf/cycle-stop

def dfs(node, path_nodes, path_edges):
    suppliers = by_buyer.get(node, [])
    if not suppliers:
        paths.append(list(path_edges))
        return
    for e in suppliers:
        nxt = e['supplier_id']
        if nxt in path_nodes:
            # cycle detected - record path up to and including this edge, then stop extending
            paths.append(path_edges + [e])
            continue
        dfs(nxt, path_nodes | {nxt}, path_edges + [e])

dfs(ROOT, {ROOT}, [])

print(f"Total root-to-leaf/cycle paths: {len(paths)}")
for p in paths:
    chain = ROOT + ' -> ' + ' -> '.join(f"{e['supplier_id']}(t{i+1},{e['share_pct']}%)" for i, e in enumerate(p))
    print(chain)

# Occurrence basis: count each (company, tier=min depth reached via any path) occurrence per unique path
# Build tier map: company_id -> set of tiers at which it appears across all paths
tier_occurrences = defaultdict(set)
node_paths = defaultdict(list)  # company -> list of (tier, path_str)
for p in paths:
    for i, e in enumerate(p):
        tier = i + 1
        supplier = e['supplier_id']
        tier_occurrences[supplier].add(tier)
        chain_str = ROOT + '->' + '->'.join(x['supplier_id'] for x in p[:i+1])
        node_paths[supplier].append((tier, chain_str))

print("\n--- Company -> tiers observed (per-path basis) ---")
for c, tiers in sorted(tier_occurrences.items()):
    print(c, sorted(tiers))

print("\n--- Min tier per company (first appearance) ---")
min_tier = {c: min(t) for c, t in tier_occurrences.items()}
for c, t in sorted(min_tier.items(), key=lambda x: x[1]):
    print(t, c)

json.dump({
    'paths': [[{'buyer': e['buyer_id'], 'supplier': e['supplier_id'], 'item': e['item'], 'share_pct': e['share_pct'], 'confidence': e['confidence']} for e in p] for p in paths],
    'min_tier': min_tier,
}, open('./workspace/1787282199-한울소재-supply-chain-risk/tier_expansion.json', 'w'), ensure_ascii=False, indent=2)
