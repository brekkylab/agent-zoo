"""fixtures.py의 12사를 원천별 스키마로 펼쳐 data/에 쓴다.

값은 fixtures에서만 온다. 여기서는 모양만 만든다 —
DART/EDGAR/GLEIF의 실제 응답 구조와 버릇(`datagen/reference/*_quirks.md`)을 재현한다.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as F  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ROOT = os.path.normpath(ROOT)


def _p(*parts):
    path = os.path.join(ROOT, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def wjson(rel, obj):
    with open(_p(rel), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def wjsonl(rel, rows):
    with open(_p(rel), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def wcsv(rel, header, rows):
    with open(_p(rel), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def won(v):
    """DART 금액 표기: 콤마 낀 문자열, 음수는 '-' 접두, 결측은 빈 문자열."""
    return "" if v is None else f"{v:,}"


by_id = {c["company_id"]: c for c in F.COMPANIES}


# ------------------------------------------------------------------ registry
def emit_dart_company():
    for c in F.COMPANIES:
        if not c["dart"]:
            continue
        rec = {"status": "000", "message": "정상", "corp_code": c["corp_code"]}
        rec.update(c["dart"])
        wjson(f"registry/dart_company/{c['corp_code']}.json", rec)


def emit_dart_corpcode():
    """corpCode.xml — 결측 stock_code가 빈 문자열이 아니라 공백 1자다(quirks ②).
    상호도 company.json과 다르다(①). 대진화학이 두 건 있다(⑩)."""
    lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<result>"]
    for c in F.COMPANIES:
        if not c["dart"]:
            continue
        lines += [
            "  <list>",
            f"    <corp_code>{c['corp_code']}</corp_code>",
            f"    <corp_name>{c['corpcode_name']}</corp_name>",
            f"    <corp_eng_name>{c['dart']['corp_name_eng']}</corp_eng_name>",
            f"    <stock_code>{c['dart']['stock_code'] or ' '}</stock_code>",
            f"    <modify_date>{c['dart']['est_dt']}</modify_date>",
            "  </list>",
        ]
    lines.append("</result>")
    with open(_p("registry/dart_corpcode.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def emit_edgar_submissions():
    for c in F.COMPANIES:
        e = c.get("edgar")
        if not e:
            continue
        rec = {
            "cik": c["cik"], "entityType": "operating", "sic": e["sic"],
            "sicDescription": e["sic_desc"], "ownerOrg": "04 Manufacturing",
            "insiderTransactionForOwnerExists": 0,
            "insiderTransactionForIssuerExists": 1,
            "name": e["name"], "tickers": e["tickers"], "exchanges": e["exchanges"],
            "ein": e["ein"], "lei": c["lei"], "description": "",
            "website": "", "investorWebsite": "", "category": "Large accelerated filer",
            "fiscalYearEnd": e["fiscal_year_end"],
            "stateOfIncorporation": e["state_inc"],
            "stateOfIncorporationDescription": "DE",
            "addresses": {
                k: {"street1": e["street1"], "street2": None, "city": e["city"],
                    "stateOrCountry": e["state"], "zipCode": e["zipcode"],
                    "stateOrCountryDescription": "NV", "isForeignLocation": 0,
                    "foreignStateTerritory": None, "country": None,
                    "countryCode": None}
                for k in ("mailing", "business")},
            "phone": "775-555-0142", "flags": "",
            "formerNames": e["former_names"],
            # filings.recent은 행 배열이 아니라 컬럼 지향 병렬 배열이다(E1)
            "filings": {"recent": {}, "files": []},
        }
        cols = {
            "accessionNumber": ["9900000101-26-000031", "9900000101-26-000007",
                                "9900000101-25-000009", "9900000101-24-000012"],
            "filingDate": ["2026-05-07", "2026-02-18", "2025-02-19", "2024-02-21"],
            "reportDate": ["2025-12-31", "2025-12-31", "2024-12-31", "2023-12-31"],
            "acceptanceDateTime": ["2026-05-07T16:31:02.000Z", "2026-02-18T17:04:55.000Z",
                                   "2025-02-19T16:48:11.000Z", "2024-02-21T17:12:39.000Z"],
            "act": ["34", "34", "34", "34"],
            "form": ["10-K/A", "10-K", "10-K", "10-K"],
            "fileNumber": ["001-40912", "001-40912", "001-40912", "001-40912"],
            "filmNumber": ["", "261204418", "251188203", "241166057"],
            "items": ["", "", "", ""],
            "core_type": ["10-K/A", "10-K", "10-K", "10-K"],
            "size": [1_884_112, 4_552_330, 4_118_775, 3_880_446],
            "isXBRL": [1, 1, 1, 1], "isInlineXBRL": [1, 1, 1, 1],
            "isXBRLNumeric": [1, 1, 1, 1],
            "primaryDocument": ["ngcl-20251231a.htm", "ngcl-20251231.htm",
                                "ngcl-20241231.htm", "ngcl-20231231.htm"],
            "primaryDocDescription": ["10-K/A", "10-K", "10-K", "10-K"],
        }
        rec["filings"]["recent"] = cols
        wjson(f"registry/edgar_submissions/{c['cik']}.json", rec)


def emit_gleif():
    """LEI 레코드. legalName이 현지어이고 영문은 otherNames에 있다(G2).
    registeredAs가 사업자등록번호이며 하이픈 포맷이 DART와 다르다(G1)."""
    recs = []
    for c in F.COMPANIES:
        g = c.get("gleif")
        if not g:
            continue
        lang = g.get("lang", "ko")
        recs.append({
            "lei": c["lei"],
            "entity": {
                "legalName": {"name": g["name_ko"], "language": lang},
                "otherNames": [{"name": g["name_en"], "language": "en",
                                "type": "ALTERNATIVE_LANGUAGE_LEGAL_NAME"}],
                "transliteratedOtherNames": [],
                "legalAddress": {"language": lang, "addressLines": [g["addr_ko"]],
                                 "addressNumber": None, "addressNumberWithinBuilding": None,
                                 "mailRouting": None, "city": g["city"],
                                 "region": g["region"], "country": c["country"],
                                 "postalCode": g["postal"]},
                "headquartersAddress": {"language": lang, "addressLines": [g["addr_ko"]],
                                        "addressNumber": None,
                                        "addressNumberWithinBuilding": None,
                                        "mailRouting": None, "city": g["city"],
                                        "region": g["region"], "country": c["country"],
                                        "postalCode": g["postal"]},
                "registeredAt": {"id": g["ra_id"], "other": None},
                "registeredAs": g["registered_as"],
                "jurisdiction": c["country"], "category": "GENERAL",
                "legalForm": {"id": g["legal_form"], "other": None},
                "associatedEntity": {"lei": None, "name": None},
                "status": g["status"],
                # INACTIVE인데 만료 사유가 비어 있다 — 실물이 그렇다(G7)
                "expiration": {"date": None, "reason": None},
                "successorEntity": {"lei": None, "name": None},
                "successorEntities": [],
                "creationDate": g["created"] + "T00:00:00Z",
                "subCategory": None,
                "otherAddresses": [{"fieldType": "OtherAddress", "language": "en",
                                    "type": "ALTERNATIVE_LANGUAGE_LEGAL_ADDRESS",
                                    "addressLines": [g["addr_en"]], "city": g["city"],
                                    "region": g["region"], "country": c["country"],
                                    "postalCode": g["postal"]}],
                "eventGroups": [],
            },
            "registration": {
                "initialRegistrationDate": g["initial_reg"] + "T00:00:00Z",
                "lastUpdateDate": g["last_update"] + "T00:00:00Z",
                "status": "ISSUED" if g["status"] == "ACTIVE" else "LAPSED",
                "nextRenewalDate": "2027-01-31T00:00:00Z",
                "managingLou": "0000MANAGINGLOU0001A0",
                "corroborationLevel": "FULLY_CORROBORATED",
                "validatedAt": {"id": g["ra_id"], "other": None},
                "validatedAs": g["registered_as"], "otherValidationAuthorities": [],
            },
            "bic": None, "conformityFlag": "CONFORMING",
        })
    wjsonl("registry/gleif_lei.jsonl", recs)

    # 관계 레코드 — 지분율이 없다(G5). LEI 없는 성진정밀은 여기 못 들어온다
    rr = []
    for parent, child, _pct, _basis, has_rr, as_of, _note in F.OWNERSHIP:
        if has_rr != "yes":
            continue
        p, ch = by_id[parent], by_id[child]
        for rtype in ("IS_DIRECTLY_CONSOLIDATED_BY", "IS_ULTIMATELY_CONSOLIDATED_BY"):
            rr.append({
                "id": f"{ch['lei']}|LEI|{rtype}|7|mock",
                "validFrom": "2025-12-22T16:00:00Z", "validTo": None,
                "relationship": {
                    "startNode": {"id": ch["lei"], "type": "LEI"},
                    "endNode": {"id": p["lei"], "type": "LEI"},
                    "type": rtype, "status": "ACTIVE",
                    "periods": [
                        {"startDate": "2019-01-01T00:00:00Z", "type": "RELATIONSHIP_PERIOD"},
                        {"startDate": "2025-01-01T00:00:00Z", "endDate": "2025-12-31T00:00:00Z",
                         "type": "ACCOUNTING_PERIOD"},
                    ],
                },
                "registration": {
                    "initialRegistrationDate": "2019-03-11T00:00:00Z",
                    "lastUpdateDate": "2026-01-14T00:00:00Z", "status": "PUBLISHED",
                    "nextRenewalDate": "2027-01-14T00:00:00Z",
                    "managingLou": "0000MANAGINGLOU0001A0",
                    "corroborationLevel": "PARTIALLY_CORROBORATED",
                    "corroborationDocuments": "ACCOUNTS_FILING",
                    "corroborationReference": None,
                },
            })
    wjsonl("registry/gleif_rr.jsonl", rr)


def emit_index():
    """세 소스를 잇는 유일한 브릿지. 이름으로는 이어지지 않는다."""
    rows = [(c["company_id"], c["lei"] or "", c["corp_code"] or "",
             c["cik"] or "", c["primary_source"], c["country"])
            for c in F.COMPANIES]
    wcsv("registry/company_index.csv",
         ["company_id", "lei", "corp_code", "cik", "primary_source", "country"], rows)
    wcsv("registry/ownership.csv", F.OWNERSHIP_COLUMNS, F.OWNERSHIP)


# ---------------------------------------------------------------- financials
def emit_dart_financials():
    layouts = {"manufacturing": F.MANUFACTURING_LAYOUT, "financial": F.FINANCIAL_LAYOUT}
    for cid, years in F.FINANCIALS.items():
        c = by_id[cid]
        if not c["dart"]:
            continue
        for year, d in years.items():
            layout = layouts[d["layout"]]
            term = d["term"]
            rows = []
            for div_key, fs_div, fs_nm in (("cfs", "CFS", "연결재무제표"),
                                           ("ofs", "OFS", "재무제표")):
                acc = d.get(div_key)
                if not acc:
                    continue
                for name, sj, ord_c, ord_o in layout:
                    if name not in acc:
                        continue
                    vals = acc[name]
                    dt = (lambda y: f"{y}.12.31 현재") if sj == "BS" \
                        else (lambda y: f"{y}.01.01 ~ {y}.12.31")
                    rows.append({
                        "rcept_no": f"{year + 1}0318{c['corp_code'][-6:]}",
                        "reprt_code": "11011", "bsns_year": str(year),
                        "corp_code": c["corp_code"],
                        "stock_code": c["dart"]["stock_code"],
                        "fs_div": fs_div, "fs_nm": fs_nm,
                        "sj_div": sj,
                        "sj_nm": "재무상태표" if sj == "BS" else "손익계산서",
                        "account_nm": name,
                        "thstrm_nm": f"제 {term} 기", "thstrm_dt": dt(year),
                        "thstrm_amount": won(vals[0]),
                        "frmtrm_nm": f"제 {term - 1} 기", "frmtrm_dt": dt(year - 1),
                        "frmtrm_amount": won(vals[1]),
                        "bfefrmtrm_nm": f"제 {term - 2} 기", "bfefrmtrm_dt": dt(year - 2),
                        "bfefrmtrm_amount": won(vals[2]),
                        "ord": str(ord_c if fs_div == "CFS" else ord_o),
                        "currency": "KRW",
                    })
            wjson(f"financials/dart_fnltt/{c['corp_code']}-{year}.json",
                  {"status": "000", "message": "정상", "list": rows})


def emit_edgar_financials():
    for cid, tags in F.EDGAR_FACTS.items():
        c = by_id[cid]
        for tag, items in tags.items():
            wjson(f"financials/edgar_facts/{c['cik']}-{tag}.json", {
                "cik": int(c["cik"]), "taxonomy": "us-gaap", "tag": tag,
                "label": tag, "description": f"Mock {tag} concept.",
                "entityName": c["edgar"]["name"],
                "units": {"USD": [{k: v for k, v in it.items() if v is not None}
                                  for it in items]},
            })


# ------------------------------------------------------------------ the rest
def emit_tables():
    wcsv("supplychain/edges.csv", F.EDGE_COLUMNS, F.EDGES)
    wcsv("risk/sanctions.csv", F.SANCTIONS_COLUMNS, F.SANCTIONS)
    wcsv("reference/industry_xwalk.csv",
         ["ksic", "sic", "naics", "note"], F.INDUSTRY_XWALK)
    fx = []
    for cur, vals in F.FX_RATES.items():
        for month, v in zip(F.FX_MONTHS, vals):
            if v is None:      # 의도된 결측. 행 자체를 만들지 않는다
                continue
            fx.append((month, cur, "KRW", f"{v:.2f}", "mock-ecos"))
    wcsv("reference/fx_rates.csv",
         ["month", "from_currency", "to_currency", "rate", "source"], sorted(fx))
    wcsv("watchlist.csv", ["company_id", "added_on", "owner"],
         [(cid, "2026-01-05", "supply-chain-team") for cid in F.WATCHLIST])


if __name__ == "__main__":
    emit_dart_company()
    emit_dart_corpcode()
    emit_edgar_submissions()
    emit_gleif()
    emit_index()
    emit_dart_financials()
    emit_edgar_financials()
    emit_tables()
    n = sum(len(f) for _, _, f in os.walk(ROOT))
    print(f"wrote {n} files under {ROOT}")
