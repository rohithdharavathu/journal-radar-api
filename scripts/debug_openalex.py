"""Quick diagnostic — test one ISSN and print the raw OpenAlex response."""
import requests

MAILTO = 'rohith.dharavathu.112@gmail.com'
BASE_URL = 'https://api.openalex.org/sources'

TEST_ISSN = '0957-4174'  # Expert Systems with Applications

# Test 1: with works_by_year
print("=== Test 1: with works_by_year ===")
r = requests.get(BASE_URL, params={
    'filter': f'issn:{TEST_ISSN}',
    'select': 'id,homepage_url,topics,works_count,works_by_year',
    'mailto': MAILTO,
}, timeout=15)
print(f"Status: {r.status_code}")
print(r.text[:500])

print()

# Test 2: without works_by_year
print("=== Test 2: without works_by_year ===")
r2 = requests.get(BASE_URL, params={
    'filter': f'issn:{TEST_ISSN}',
    'select': 'id,homepage_url,topics,works_count',
    'mailto': MAILTO,
}, timeout=15)
print(f"Status: {r2.status_code}")
print(r2.text[:500])
