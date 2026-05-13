"""
Populate waiver_info JSONB for journals whose publishers have known waiver programs.
Also sets review_type based on publisher pattern.
Batch-updates 500 journals at a time.
"""
import json
import os
import re
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

PUBLISHER_WAIVERS = {
    "IEEE": {
        "has_waiver": True,
        "countries_eligible": ["India", "Pakistan", "Bangladesh", "Nigeria", "Kenya"],
        "discount": "25–50% APC reduction for lower-middle-income countries",
        "how_to_apply": "Request during submission via IEEE Author Center",
        "url": "https://ieeeauthorcenter.ieee.org/publish-with-ieee/author-education-resources/guidelines-and-policies/policy-posting-your-article/ieee-open-access-publishing-options/",
    },
    "Springer": {
        "has_waiver": True,
        "countries_eligible": ["India", "64 low/lower-middle income countries"],
        "discount": "Full APC waiver for eligible countries",
        "how_to_apply": "Automatically applied during submission if author affiliation is in eligible country",
        "url": "https://www.springernature.com/gp/open-research/policies/journal-policies/apc-waiver-countries",
    },
    "Elsevier": {
        "has_waiver": True,
        "countries_eligible": ["45 low-income countries (not India currently)"],
        "discount": "Full or partial waiver",
        "how_to_apply": "Request via journal editorial office",
        "url": "https://www.elsevier.com/about/policies/apc-waiver-countries",
    },
    "MDPI": {
        "has_waiver": True,
        "countries_eligible": ["All — based on financial need, not country"],
        "discount": "Partial waiver, case by case",
        "how_to_apply": "Apply during submission, provide justification",
        "url": "https://www.mdpi.com/about/apc",
    },
    "Wiley": {
        "has_waiver": True,
        "countries_eligible": ["Low-income countries (World Bank list)"],
        "discount": "Full waiver",
        "how_to_apply": "Contact journal editorial office before submission",
        "url": "https://authorservices.wiley.com/open-research/open-access/for-authors/waivers-and-discounts.html",
    },
    "Taylor & Francis": {
        "has_waiver": True,
        "countries_eligible": ["Research4Life countries including India for some journals"],
        "discount": "Full or 50% waiver depending on country tier",
        "how_to_apply": "Automatically applied or request via submission system",
        "url": "https://authorservices.taylorandfrancis.com/publishing-open-access/open-access-cost-finder/",
    },
}

# Publisher → review_type mapping (pattern match on publisher name)
REVIEW_TYPE_MAP = [
    (r"ieee", "double_blind"),
    (r"acm\b|association for computing machinery", "double_blind"),
    (r"nature\b|springer nature", "single_blind"),
    (r"mdpi", "single_blind"),
    (r"elsevier", "single_blind"),
    (r"wiley", "single_blind"),
    (r"taylor|routledge", "single_blind"),
]


def match_publisher_waiver(publisher: str) -> dict | None:
    pub_lower = publisher.lower()
    for key, info in PUBLISHER_WAIVERS.items():
        if key.lower() in pub_lower:
            return info
    return None


def match_review_type(publisher: str) -> str | None:
    pub_lower = publisher.lower()
    for pattern, rtype in REVIEW_TYPE_MAP:
        if re.search(pattern, pub_lower):
            return rtype
    return None


def main():
    print("Fetching all journals (id, publisher)...")
    page_size = 1000
    offset = 0
    all_journals = []

    while True:
        result = (
            supabase.from_("journals")
            .select("id, publisher")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        all_journals.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    print(f"  {len(all_journals)} journals loaded")

    # Build update batches grouped by waiver_info + review_type
    waiver_updates: dict[str, list[int]] = defaultdict(list)  # json-serialized waiver → ids
    review_updates: dict[str, list[int]] = defaultdict(list)  # type → ids

    for j in all_journals:
        pub = j.get("publisher") or ""
        if not pub:
            continue
        waiver = match_publisher_waiver(pub)
        if waiver:
            key = json.dumps(waiver, sort_keys=True)
            waiver_updates[key].append(j["id"])

        rtype = match_review_type(pub)
        if rtype:
            review_updates[rtype].append(j["id"])

    # Apply waiver updates (batch by 500)
    print("Updating waiver_info...")
    total_waiver = sum(len(v) for v in waiver_updates.values())
    done = 0
    for waiver_json, ids in waiver_updates.items():
        waiver_obj = json.loads(waiver_json)
        for i in range(0, len(ids), 500):
            batch = ids[i : i + 500]
            supabase.from_("journals").update({"waiver_info": waiver_obj}).in_("id", batch).execute()
            done += len(batch)
            print(f"  waiver: {done}/{total_waiver}")

    # Apply review_type updates
    print("Updating review_type...")
    total_review = sum(len(v) for v in review_updates.values())
    done = 0
    for rtype, ids in review_updates.items():
        for i in range(0, len(ids), 500):
            batch = ids[i : i + 500]
            supabase.from_("journals").update({"review_type": rtype}).in_("id", batch).execute()
            done += len(batch)
            print(f"  review_type={rtype}: {done}/{total_review}")

    print(f"Done. {total_waiver} waiver updates, {total_review} review_type updates.")


if __name__ == "__main__":
    main()
