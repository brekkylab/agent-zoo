"""
재무 건전성 분석.
CATALOG.md §3.1(fs_div 재적용 필수), §3.2(account_nm+ord dedupe), §3.3(문자열->숫자 변환) 지침 준수.
대상: 99000101(한울소재, FY2025 CFS/OFS), 99000512(한울캐피탈, FY2025 CFS, 금융업 계정),
      99000427(성진정밀, FY2024 OFS만 존재).
"""
import json

def load(path):
    with open(path) as f:
        data = json.load(f)
    rows = data['list']
    seen = set()
    recs = []
    for r in rows:
        key = (r['fs_div'], r['sj_div'], r['account_nm'], r['ord'])
        if key in seen:
            continue
        seen.add(key)
        recs.append(r)
    by_fs = {}
    for r in recs:
        by_fs.setdefault(r['fs_div'], {})[r['account_nm']] = r
    return by_fs

def amt(r, k='thstrm_amount'):
    return int(r[k].replace(',', ''))

def ratios(accts, label):
    ca = amt(accts['유동자산'])
    cl = amt(accts['유동부채'])
    tl = amt(accts['부채총계'])
    te = amt(accts['자본총계'])
    rev = amt(accts['매출액'])
    op = amt(accts['영업이익'])
    ni = amt(accts['당기순이익(손실)'])
    rev_prior = amt(accts['매출액'], 'frmtrm_amount')
    print(f"--- {label} ---")
    print('유동비율:', round(ca/cl*100,1), '%')
    print('부채비율:', round(tl/te*100,1), '%')
    print('영업이익률:', round(op/rev*100,1), '%')
    print('순이익률:', round(ni/rev*100,1), '%')
    print('매출YoY:', round((rev-rev_prior)/rev_prior*100,1), '%')

hanul = load('./data/financials/dart_fnltt/99000101-2025.json')
ratios(hanul['CFS'], '한울소재 CFS FY2025')
ratios(hanul['OFS'], '한울소재 OFS FY2025')

cap = load('./data/financials/dart_fnltt/99000512-2025.json')
accts = cap['CFS']
tl = amt(accts['부채총계']); te = amt(accts['자본총계'])
print('--- 한울캐피탈 CFS FY2025 ---')
print('부채비율:', round(tl/te*100,1), '%')
print('자산총계:', accts['자산총계']['thstrm_amount'])

sj = load('./data/financials/dart_fnltt/99000427-2024.json')
ratios(sj['OFS'], '성진정밀 OFS FY2024 (최신연도)')
