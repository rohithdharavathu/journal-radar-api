"""JournalRadar AI Service — FastAPI

Endpoints:
  POST /match              — semantic journal search via OpenAI embeddings
  POST /scope-fit          — Claude scope fit analysis for a single journal
  POST /scope-fit-multi    — scope fit for up to 5 journals concurrently
  GET  /similar/{id}       — find similar journals by stored embedding
  GET  /autocomplete       — journal name suggestions
  GET  /health             — liveness probe
"""
import asyncio
import hashlib
import json
import os
from typing import Optional

import anthropic
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
app = FastAPI(title="JournalRadar AI", version="4.0")
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
anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

API_SECRET = os.environ.get("API_SECRET_KEY", "")

QUARTILE_RANK = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

SUBJECT_AREAS = [
    "Medicine", "Arts and Humanities", "Social Sciences",
    "Agricultural and Biological Sciences", "Computer Science",
    "Biochemistry, Genetics and Molecular Biology", "Engineering",
    "Business, Management and Accounting", "Earth and Planetary Sciences",
    "Mathematics", "Economics, Econometrics and Finance", "Psychology",
    "Health Professions", "Environmental Science", "Chemistry",
    "Chemical Engineering", "Energy", "Immunology and Microbiology",
    "Materials Science", "Dentistry", "Physics and Astronomy", "Nursing",
    "Neuroscience", "Veterinary", "Pharmacology, Toxicology and Pharmaceutics",
    "Decision Sciences", "Multidisciplinary",
]

CLASSIFY_PROMPT = (
    "You are a research domain classifier. Given an abstract, return ONLY the single most "
    "relevant subject area from the list below — exact string, nothing else.\n\n"
    + "\n".join(f"- {s}" for s in SUBJECT_AREAS)
)


# ─── Auth ────────────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(None)):
    if not API_SECRET:
        return  # dev mode
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ─── Helpers ─────────────────────────────────────────────────────────────────

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
    return f"Some overlap with {area} research in this journal"


def score_to_label(score: str) -> str:
    return {
        "strong": "Strong Fit ✅",
        "moderate": "Moderate Fit ⚠️",
        "weak": "Weak Fit ❌",
        "no_fit": "Not a Fit 🚫",
    }.get(score, "Unknown")


# ─── Models ──────────────────────────────────────────────────────────────────

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


class ScopeFitRequest(BaseModel):
    journal_id: int
    abstract: str

    @field_validator("abstract")
    @classmethod
    def validate_abstract(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 50:
            raise ValueError("Abstract must be at least 50 characters")
        return v[:6000]


class MultiFitRequest(BaseModel):
    journal_ids: list[int]
    abstract: str

    @field_validator("journal_ids")
    @classmethod
    def validate_ids(cls, v: list[int]) -> list[int]:
        if len(v) > 5:
            raise ValueError("Maximum 5 journals at once")
        if len(v) == 0:
            raise ValueError("At least 1 journal required")
        return v

    @field_validator("abstract")
    @classmethod
    def validate_abstract(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 50:
            raise ValueError("Abstract must be at least 50 characters")
        return v[:6000]


# ─── Scope fit core logic ─────────────────────────────────────────────────────

async def _scope_fit_internal(journal_id: int, abstract: str) -> dict:
    """
    Core scope fit logic. Checks cache first, calls Claude if not cached.
    Returns a dict with fit_score, fit_label, reasoning, emphasise, concern, from_cache.
    """
    abstract_hash = hashlib.sha256(abstract.encode()).hexdigest()[:16]

    # Cache check
    cached = supabase.table("scope_fit_cache") \
        .select("*") \
        .eq("journal_id", journal_id) \
        .eq("abstract_hash", abstract_hash) \
        .execute()

    if cached.data:
        row = cached.data[0]
        return {
            "fit_score": row["fit_score"],
            "fit_label": score_to_label(row["fit_score"]),
            "reasoning": row["fit_reason"],
            "emphasise": row.get("fit_tips") or "",
            "concern": None,
            "from_cache": True,
        }

    # Fetch journal
    journal_result = supabase.table("journals") \
        .select("title, subject_area, subject_category, publisher, aims_scope") \
        .eq("id", journal_id) \
        .single() \
        .execute()

    if not journal_result.data:
        raise HTTPException(404, f"Journal {journal_id} not found")

    journal = journal_result.data

    journal_context = (
        f"Journal: {journal['title']}\n"
        f"Publisher: {journal.get('publisher', 'Unknown')}\n"
        f"Subject Area: {journal.get('subject_area', 'Unknown')}\n"
        f"Subject Category: {journal.get('subject_category', 'Unknown')}\n"
    )
    if journal.get("aims_scope"):
        journal_context += f"\nAims & Scope:\n{journal['aims_scope'][:2000]}"
    else:
        journal_context += "\nNote: Full aims & scope not available. Use your knowledge of this journal."

    prompt = f"""You are an expert academic journal editor with 20 years of experience.

Analyze whether this paper abstract fits the journal's scope.

{journal_context}

PAPER ABSTRACT:
{abstract}

Respond in this EXACT JSON format (no markdown, no text outside JSON):
{{
  "fit_score": "strong" | "moderate" | "weak" | "no_fit",
  "reasoning": "2-3 sentence explanation specific to this journal and abstract",
  "emphasise": "1-2 sentences on what to highlight in cover letter and introduction",
  "concern": "1 sentence on the main risk or mismatch, or null if strong fit"
}}

Be specific. Reference the journal by name. Reference specific elements of the abstract. Do not be generic."""

    try:
        message = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
    except Exception as e:
        raise HTTPException(502, f"Analysis failed: {e}")

    fit_score = result.get("fit_score", "moderate")
    reasoning = result.get("reasoning", "")
    emphasise = result.get("emphasise", "")
    concern = result.get("concern")

    # Cache (non-fatal if fails)
    try:
        supabase.table("scope_fit_cache").insert({
            "journal_id": journal_id,
            "abstract_hash": abstract_hash,
            "fit_score": fit_score,
            "fit_reason": reasoning,
            "fit_tips": emphasise,
        }).execute()
    except Exception:
        pass

    return {
        "fit_score": fit_score,
        "fit_label": score_to_label(fit_score),
        "reasoning": reasoning,
        "emphasise": emphasise,
        "concern": concern,
        "from_cache": False,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

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
            if row_quartile and QUARTILE_RANK.get(row_quartile, 99) > QUARTILE_RANK[body.min_quartile]:
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
            "match_reason": generate_match_reason(sim, row.get("subject_area"), row.get("subject_category")),
        })
        if len(matches) >= body.limit:
            break

    return {"detected_domain": subject_filter, "results": matches}


@app.post("/scope-fit")
@limiter.limit("20/minute")
async def check_scope_fit(request: Request, body: ScopeFitRequest, _=Depends(verify_api_key)):
    """Analyze whether a paper abstract fits a journal's scope."""
    return await _scope_fit_internal(body.journal_id, body.abstract)


@app.post("/scope-fit-multi")
@limiter.limit("10/minute")
async def check_scope_fit_multi(request: Request, body: MultiFitRequest, _=Depends(verify_api_key)):
    """Check abstract fit against up to 5 journals concurrently. Returns ranked results."""
    SCORE_ORDER = {"strong": 0, "moderate": 1, "weak": 2, "no_fit": 3}

    async def check_one(journal_id: int) -> dict:
        try:
            result = await _scope_fit_internal(journal_id, body.abstract)
            return {"journal_id": journal_id, **result}
        except HTTPException as e:
            return {"journal_id": journal_id, "error": e.detail, "fit_score": "no_fit"}
        except Exception as e:
            return {"journal_id": journal_id, "error": str(e), "fit_score": "no_fit"}

    results = await asyncio.gather(*[check_one(jid) for jid in body.journal_ids])
    results = sorted(results, key=lambda r: SCORE_ORDER.get(r.get("fit_score", "no_fit"), 4))
    return results


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

    return [r for r in (similar.data or []) if r["id"] != journal_id][:8]


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
    return {"status": "ok", "version": "4.0"}
