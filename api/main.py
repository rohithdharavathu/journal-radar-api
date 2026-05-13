"""JournalRadar AI Service — FastAPI

Endpoints:
  POST /match          — classify abstract domain, embed, cosine search within domain, return top N
  GET  /similar/{id}  — find journals similar to a given journal by embedding
  GET  /autocomplete  — journal name suggestions as user types
  GET  /health        — liveness probe
"""
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from supabase import create_client

load_dotenv()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="JournalRadar AI", version="3.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = [
    "https://frontend-omega-green-75.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

API_SECRET = os.environ.get("API_SECRET_KEY", "")

QUARTILE_RANK = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

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


def verify_api_key(x_api_key: str = Header(None)):
    if not API_SECRET:
        return  # dev mode — skip validation
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid API key")


def classify_subject(abstract: str) -> Optional[str]:
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": abstract[:2000]},
            ],
            max_tokens=20,
            temperature=0,
            timeout=8.0,
        )
        classified = resp.choices[0].message.content.strip()
        return classified if classified in SUBJECT_AREAS else None
    except Exception:
        return None


def generate_match_reason(score: float, subject_area: Optional[str], subject_category: Optional[str]) -> str:
    pct = round(score * 100)
    area = subject_area or "your research area"
    category = subject_category or ""

    if pct >= 80:
        return f"Highly relevant — papers on {category or area} are frequently published here"
    elif pct >= 65:
        return f"Good match — your topic aligns with {category or area} literature in this journal"
    elif pct >= 50:
        return f"Related work in {area} has been published here"
    else:
        return f"Some overlap with {area} research in this journal"


class MatchRequest(BaseModel):
    abstract: str
    max_apc_usd: Optional[float] = None
    min_quartile: Optional[str] = None
    subject_area: Optional[str] = None
    limit: int = 10

    @field_validator("subject_area")
    @classmethod
    def validate_subject_area(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in SUBJECT_AREAS:
            raise ValueError("subject_area must be one of the known domains")
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
@limiter.limit("30/minute")
async def match_journals(request: Request, body: MatchRequest, _=Depends(verify_api_key)):
    subject_filter = body.subject_area
    if not subject_filter:
        subject_filter = classify_subject(body.abstract)

    try:
        emb = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=body.abstract,
            timeout=10.0,
        )
        vector = emb.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")

    vector_str = "[" + ",".join(str(v) for v in vector) + "]"

    fetch_multiplier = 10 if (body.min_quartile or body.max_apc_usd is not None) else 5
    try:
        result = supabase.rpc("match_journals", {
            "query_embedding": vector_str,
            "match_count": body.limit * fetch_multiplier,
            "subject_filter": subject_filter,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database error: {e}")

    MIN_SIMILARITY = 0.15
    matches = []
    for row in result.data or []:
        sim = float(row.get("similarity", 0))
        if sim < MIN_SIMILARITY:
            continue

        if body.min_quartile:
            row_quartile = row.get("quartile")
            if row_quartile:
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

        matches.append({
            **row,
            "similarity_score": round(sim, 4),
            "detected_domain": subject_filter,
            "match_reason": generate_match_reason(
                sim,
                row.get("subject_area"),
                row.get("subject_category"),
            ),
        })

        if len(matches) >= body.limit:
            break

    return {
        "detected_domain": subject_filter,
        "results": matches,
    }


@app.get("/similar/{journal_id}")
@limiter.limit("30/minute")
async def similar_journals(journal_id: int, request: Request, _=Depends(verify_api_key)):
    result = supabase.table("journals") \
        .select("embedding, title") \
        .eq("id", journal_id) \
        .single() \
        .execute()

    if not result.data or not result.data.get("embedding"):
        raise HTTPException(404, "Journal not found or has no embedding")

    embedding = result.data["embedding"]
    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"

    similar = supabase.rpc("match_journals", {
        "query_embedding": vector_str,
        "match_count": 9,
    }).execute()

    filtered = [r for r in (similar.data or []) if r["id"] != journal_id][:8]
    return filtered


@app.get("/autocomplete")
@limiter.limit("60/minute")
async def autocomplete(q: str, request: Request, limit: int = 6, _=Depends(verify_api_key)):
    if len(q.strip()) < 2:
        return {"suggestions": []}

    result = supabase.table("journals") \
        .select("id, title, publisher, quartile, subject_area") \
        .ilike("title", f"%{q}%") \
        .eq("is_active", True) \
        .order("sjr_score", desc=True) \
        .limit(max(1, min(limit, 10))) \
        .execute()

    return {"suggestions": result.data or []}


@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0"}
