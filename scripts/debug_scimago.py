# scripts/debug_scimago.py
import json

with open('data/scimago_clean.json', encoding='utf-8') as f:
    data = json.load(f)

print("First 3 records:")
for j in data[:3]:
    print(j)

print(f"\nQuartile values (first 20):")
for j in data[:20]:
    print(f"  '{j.get('quartile')}'")

print(f"\nNull quartiles: {sum(1 for j in data if not j.get('quartile'))}/{len(data)}")