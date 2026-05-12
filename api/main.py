"""JournalRadar AI Service — FastAPI

Endpoints:
  POST /match  — classify abstract domain, embed, cosine search within domain, return top N
  GET  /health — liveness probe
  GET  /debug  — connection test

Rate limit: 10 requests/minute per IP
"""
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from supabase import create_client

load_dotenv()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="JournalRadar AI", version="2.1")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

QUARTILE_RANK = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Exact subject_area values from journals table
SUBJECT_AREAS = [
    "Medicine",
    "Arts and Humanities",
    "Social Sciences",
    "Agricultural and Biological Sciences",
    "Computer Science",
    "Biochemistry, Genetics and Molecular Biology",
    "Engineering",
    "Business, Management and Accounting",
    "Earth and Planetary Sciences",
    "Mathematics",
    "Economics, Econometrics and Finance",
    "Psychology",
    "Health Professions",
    "Environmental Science",
    "Chemistry",
    "Chemical Engineering",
    "Energy",
    "Immunology and Microbiology",
    "Materials Science",
    "Dentistry",
    "Physics and Astronomy",
    "Nursing",
    "Neuroscience",
    "Veterinary",
    "Pharmacology, Toxicology and Pharmaceutics",
    "Decision Sciences",
    "Multidisciplinary",
]

CLASSIFY_PROMPT = (
    "You are a research domain classifier. Given an abstract, return ONLY the single most "
    "relevant subject area from the list below — exact string, nothing else.\n\n"
    + "\n".join(f"- {s}" for s in SUBJECT_AREAS)
)


def classify_subject(abstract: str) -> Optional[str]:
    """Use GPT-4o-mini to map the abstract to one subject area from the fixed list."""
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": abstract[:2000]},
            ],
            max_tokens=20,
            temperature=0,
        )
        classified = resp.choices[0].message.content.strip()
        return classified if classified in SUBJECT_AREAS else None
    except Exception:
        return None


class MatchRequest(BaseModel):
    abstract: str
    max_apc_usd: Optional[float] = None
    min_quartile: Optional[str] = None
    subject_area: Optional[str] = None  # override auto-classification
    limit: int = 10

    @field_validator("subject_area")
    @classmethod
    def validate_subject_area(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in SUBJECT_AREAS:
            raise ValueError(f"subject_area must be one of the known domains")
        return v

    @field_validator("abstract")
    @classmethod
    def validate_abstract(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Query must be at least 3 characters")
        return v[:8000]

    @field_validator("min_quartile")
    @classmethod
    def validate_quartile(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in QUARTILE_RANK:
            raise ValueError("min_quartile must be Q1, Q2, Q3, or Q4")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        return max(1, min(v, 50))


@app.post("/match")
@limiter.limit("10/minute")
async def match_journals(request: Request, body: MatchRequest):
    # Step 1: Classify subject domain (auto or manual override)
    subject_filter = body.subject_area
    if not subject_filter:
        subject_filter = classify_subject(body.abstract)

    # Step 2: Generate embedding from abstract
    try:
        emb = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=body.abstract,
        )
        vector = emb.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")

    vector_str = "[" + ",".join(str(v) for v in vector) + "]"

    # Step 3: Vector search within the classified subject domain
    # Over-fetch more when additional filters will further reduce results
    fetch_multiplier = 10 if (body.min_quartile or body.max_apc_usd is not None) else 5
    try:
        result = supabase.rpc("match_journals", {
            "query_embedding": vector_str,
            "match_count": body.limit * fetch_multiplier,
            "subject_filter": subject_filter,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database error: {e}")

    # Step 4: Post-filter, threshold, format
    MIN_SIMILARITY = 0.15
    matches = []
    for row in result.data or []:
        sim = float(row.get("similarity", 0))
        if sim < MIN_SIMILARITY:
            continue

        if body.min_quartile:
            row_quartile = row.get("quartile")
            if row_quartile:  # skip journals with no quartile only when filtering
                if QUARTILE_RANK.get(row_quartile, 99) > QUARTILE_RANK[body.min_quartile]:
                    continue

        if body.max_apc_usd is not None:
            apc = row.get("apc_amount_usd")
            if apc is not None:
                try:
                    if float(apc) > body.max_apc_usd:
                        continue
                except (ValueError, TypeError):
                    pass

        category = row.get("subject_category") or row.get("subject_area") or "your field"
        matches.append({
            **row,
            "similarity_score": round(sim, 4),
            "detected_domain": subject_filter,
            "match_reason": f"Semantic match in {category}",
        })

        if len(matches) >= body.limit:
            break

    return {
        "detected_domain": subject_filter,
        "results": matches,
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1"}


@app.get("/debug")
async def debug():
    try:
        emb = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input="test deepfake detection"
        )
        vector = emb.data[0].embedding
        vector_str = "[" + ",".join(str(v) for v in vector) + "]"
    except Exception as e:
        return {"error": f"OpenAI failed: {e}"}

    try:
        result = supabase.rpc("match_journals", {
            "query_embedding": vector_str,
            "match_count": 3,
            "subject_filter": "Computer Science",
        }).execute()
        top = result.data[0] if result.data else None
    except Exception as e:
        return {"openai": "ok", "error": f"Supabase failed: {e}"}

    classified = classify_subject("deepfake detection using transformers and frequency domain analysis")

    return {
        "openai": "ok",
        "supabase": "ok",
        "classify_test": classified,
        "top_match": top.get("title") if top else None,
        "top_similarity": top.get("similarity") if top else None,
    }
