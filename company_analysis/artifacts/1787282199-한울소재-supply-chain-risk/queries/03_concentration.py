import csv, json
from collections import defaultdict

edges = list(csv.DictReader(open('./data/supplychain/edges.csv')))
for e in edges:
    e['share_pct'] = float(e['share_pct'])

idx = {c['company_id']: c for c in csv.DictReader(open('./data/registry/company_index.csv'))}

ROOT = 'kr-hanul-materials'

# Tier-1 direct supplier concentration (buyer's share of procurement)
print("=== Tier-1 direct suppliers of 한울소재 (buyer share of procurement) ===")
t1 = [e for e in edges if e['buyer_id'] == ROOT]
total_t1 = sum(e['share_pct'] for e in t1)
for e in sorted(t1, key=lambda x: -x['share_pct']):
    country = idx[e['supplier_id']]['country']
    print(f"{e['supplier_id']:28s} {country}  item={e['item']:12s} share={e['share_pct']}%  relation={e['relation_type']}")
print(f"sum of tier-1 share_pct = {total_t1}% (share is buyer's % of procurement value for that item/relation, not necessarily summing to 100 across items)")

# country rollup at tier1
by_country = defaultdict(float)
for e in t1:
    by_country[idx[e['supplier_id']]['country']] += e['share_pct']
print("\nTier-1 share_pct by supplier country:", dict(by_country))

# HHI-like concentration index on tier-1 shares (normalize to sum=100 for index purposes)
shares_norm = [e['share_pct'] / total_t1 * 100 for e in t1]
hhi = sum(s**2 for s in shares_norm)
print(f"\nTier-1 HHI (normalized shares, sum=100): {hhi:.1f} (10000=monopoly, >2500=highly concentrated by DOJ/FTC convention)")

# Effective upstream exposure: trace lithium-related HS codes to see how many independent
# tier-1 paths ultimately depend on the same tier-3 miner (cn-yuxi-mining)
print("\n=== Dependency fan-in on cn-yuxi-mining (raw lithium concentrate) ===")
by_buyer = defaultdict(list)
for e in edges:
    by_buyer[e['buyer_id']].append(e)

paths_to_yuxi = []
def dfs(node, path_nodes, path_edges):
    for e in by_buyer.get(node, []):
        nxt = e['supplier_id']
        if nxt in path_nodes:
            continue
        newpath = path_edges + [e]
        if nxt == 'cn-yuxi-mining':
            paths_to_yuxi.append(newpath)
        else:
            dfs(nxt, path_nodes | {nxt}, newpath)

dfs(ROOT, {ROOT}, [])
for p in paths_to_yuxi:
    chain = ' -> '.join([ROOT] + [e['supplier_id'] for e in p])
    print(chain)
print(f"\n{len(paths_to_yuxi)} distinct supply paths from 한울소재 all converge on the single tier-3 miner cn-yuxi-mining (China, Yunnan) for 리튬 정광.")

# country distribution across ALL nodes appearing anywhere in the expansion (unique companies, node-basis not path-basis)
all_nodes = set()
for e in edges:
    all_nodes.add(e['buyer_id']); all_nodes.add(e['supplier_id'])
# restrict to those reachable from hanul-materials (from tier expansion file)
reach = json.load(open('./workspace/1787282199-한울소재-supply-chain-risk/tier_expansion.json'))
companies_reached = set(reach['min_tier'].keys())
print("\n=== Countries of unique companies reachable from 한울소재 (any tier, node-basis) ===")
country_count = defaultdict(list)
for c in companies_reached:
    country_count[idx[c]['country']].append(c)
for country, comps in country_count.items():
    print(country, comps)
