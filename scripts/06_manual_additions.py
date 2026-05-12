"""Upsert priority journals with hand-verified data.
Update if ISSN exists in DB, insert if not.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

root = Path(__file__).parent.parent
for _p in [root / 'frontend' / '.env.local', root / '.env.local', root / '.env']:
    if _p.exists():
        load_dotenv(_p, override=False)

PRIORITY_JOURNALS = [
    {
        "title": "IEEE Transactions on Information Forensics and Security",
        "issn_print": "1556-6013", "issn_electronic": "1556-6021",
        "publisher": "IEEE", "country": "United States",
        "quartile": "Q1", "sjr_score": 2.87, "h_index": 158,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Computer Science Applications",
        "homepage_url": "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=10206",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Pattern Recognition",
        "issn_print": "0031-3203", "issn_electronic": "1873-5142",
        "publisher": "Elsevier", "country": "United Kingdom",
        "quartile": "Q1", "sjr_score": 2.49, "h_index": 202,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://www.sciencedirect.com/journal/pattern-recognition",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Expert Systems with Applications",
        "issn_print": "0957-4174", "issn_electronic": "1873-6793",
        "publisher": "Elsevier", "country": "United Kingdom",
        "quartile": "Q1", "sjr_score": 2.48, "h_index": 242,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://www.sciencedirect.com/journal/expert-systems-with-applications",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Image and Vision Computing",
        "issn_print": "0262-8856", "issn_electronic": "1872-8138",
        "publisher": "Elsevier", "country": "United Kingdom",
        "quartile": "Q1", "sjr_score": 1.24, "h_index": 128,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Computer Vision",
        "homepage_url": "https://www.sciencedirect.com/journal/image-and-vision-computing",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Computer Vision and Image Understanding",
        "issn_print": "1077-3142", "issn_electronic": "1090-235X",
        "publisher": "Elsevier", "country": "United States",
        "quartile": "Q1", "sjr_score": 1.18, "h_index": 149,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Computer Vision",
        "homepage_url": "https://www.sciencedirect.com/journal/computer-vision-and-image-understanding",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Information Fusion",
        "issn_print": "1566-2535", "issn_electronic": "1872-6305",
        "publisher": "Elsevier", "country": "United Kingdom",
        "quartile": "Q1", "sjr_score": 4.15, "h_index": 116,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://www.sciencedirect.com/journal/information-fusion",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Neural Computing and Applications",
        "issn_print": "0941-0643", "issn_electronic": "1433-3058",
        "publisher": "Springer", "country": "United Kingdom",
        "quartile": "Q2", "sjr_score": 0.93, "h_index": 134,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://link.springer.com/journal/521",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Pattern Recognition Letters",
        "issn_print": "0167-8655", "issn_electronic": "1872-7344",
        "publisher": "Elsevier", "country": "Netherlands",
        "quartile": "Q2", "sjr_score": 0.89, "h_index": 131,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://www.sciencedirect.com/journal/pattern-recognition-letters",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "IEEE Access",
        "issn_print": "2169-3536", "issn_electronic": "2169-3536",
        "publisher": "IEEE", "country": "United States",
        "quartile": "Q2", "sjr_score": 0.96, "h_index": 204,
        "apc_amount_usd": 2160, "publishing_model": "gold_oa",
        "apc_display": "$2,160",
        "subject_area": "Computer Science",
        "subject_category": "General Computer Science",
        "homepage_url": "https://ieeeaccess.ieee.org/",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Forensic Science International: Digital Investigation",
        "issn_print": "2666-2817", "issn_electronic": "2666-2825",
        "publisher": "Elsevier", "country": "Netherlands",
        "quartile": "Q2", "sjr_score": 0.72, "h_index": 38,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Computer Science Applications",
        "homepage_url": "https://www.sciencedirect.com/journal/forensic-science-international-digital-investigation",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Multimedia Tools and Applications",
        "issn_print": "1380-7501", "issn_electronic": "1573-7721",
        "publisher": "Springer", "country": "United States",
        "quartile": "Q3", "sjr_score": 0.42, "h_index": 98,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Media Technology",
        "homepage_url": "https://link.springer.com/journal/11042",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "Applied Intelligence",
        "issn_print": "0924-669X", "issn_electronic": "1573-7497",
        "publisher": "Springer", "country": "Netherlands",
        "quartile": "Q2", "sjr_score": 0.98, "h_index": 86,
        "apc_amount_usd": 0, "publishing_model": "subscription",
        "apc_display": "No author fee",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://link.springer.com/journal/10489",
        "is_active": True, "is_scopus": True, "is_doaj": False,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
    {
        "title": "CAAI Artificial Intelligence Research",
        "issn_print": "2771-0920", "issn_electronic": "2771-0939",
        "publisher": "CAAI / Science Partner Journals", "country": "China",
        "quartile": "Q2", "sjr_score": 0.85, "h_index": 22,
        "apc_amount_usd": 0, "publishing_model": "diamond_oa",
        "apc_display": "No author fee (Open Access)",
        "subject_area": "Computer Science",
        "subject_category": "Artificial Intelligence",
        "homepage_url": "https://spj.science.org/journal/airesearch",
        "is_active": True, "is_scopus": True, "is_doaj": True,
        "data_confidence": "high",
        "data_sources": {"quartile": "manual", "apc": "manual"},
    },
]


def main():
    url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
    key = (
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        or os.environ.get('SUPABASE_SERVICE_KEY')
        or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        or os.environ.get('SUPABASE_KEY')
    )
    supabase = create_client(url, key)

    for j in PRIORITY_JOURNALS:
        try:
            existing = supabase.table('journals')\
                .select('id')\
                .eq('issn_print', j['issn_print'])\
                .execute()

            if existing.data:
                journal_id = existing.data[0]['id']
                supabase.table('journals').update(j).eq('id', journal_id).execute()
                print(f"Updated:  {j['title']}")
            else:
                supabase.table('journals').insert(j).execute()
                print(f"Inserted: {j['title']}")
        except Exception as e:
            print(f"ERROR on {j['title']}: {e}")

    print(f"\nDone. {len(PRIORITY_JOURNALS)} priority journals upserted.")


if __name__ == '__main__':
    main()
