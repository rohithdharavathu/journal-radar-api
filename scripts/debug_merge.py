# scripts/debug_merge.py
import json

with open('data/scimago_clean.json', encoding='utf-8') as f:
    scimago = json.load(f)

with open('data/doaj_clean.json', encoding='utf-8') as f:
    doaj = json.load(f)

# Check ISSN formats
print("=== SCIMAGO ISSN SAMPLES ===")
for j in scimago[:5]:
    print(f"  print: '{j.get('issn_print')}' | electronic: '{j.get('issn_electronic')}'")

print("\n=== DOAJ ISSN SAMPLES ===")
for j in doaj[:5]:
    print(f"  print: '{j.get('issn_print')}' | electronic: '{j.get('issn_electronic')}'")

# Check match rate
doaj_issns = set()
for j in doaj:
    if j.get('issn_print'): doaj_issns.add(j['issn_print'])
    if j.get('issn_electronic'): doaj_issns.add(j['issn_electronic'])

matched = 0
for j in scimago:
    if j.get('issn_print') in doaj_issns or j.get('issn_electronic') in doaj_issns:
        matched += 1

print(f"\n=== MATCH RATE ===")
print(f"Scimago total: {len(scimago)}")
print(f"DOAJ total: {len(doaj)}")
print(f"Matched: {matched} ({matched/len(scimago)*100:.1f}%)")