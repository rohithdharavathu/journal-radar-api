"""JournalRadar AI Service — FastAPI

Endpoints:
  POST /match  — embed abstract, cosine search journals, post-filter, return top N
  GET  /health — liveness probe

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
app = FastAPI(title="JournalRadar AI", version="2.0")
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


class MatchRequest(BaseModel):
    abstract: str
    max_apc_usd: Optional[float] = None
    min_quartile: Optional[str] = None
    limit: int = 10

    @field_validator("abstract")
    @classmethod
    def validate_abstract(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 50:
            raise ValueError("Abstract must be at least 50 characters")
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
    # Step 1: Generate embedding from abstract
    try:
        emb = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=body.abstract,
        )
        vector = emb.data[0].embedding  # plain Python list of 1536 floats
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding error: {e}")

    # Step 2: Convert vector to string format for pgvector RPC
    # supabase-py sends lists as JSON arrays but PostgreSQL vector type
    # requires string format "[0.1,0.2,...]" for correct casting
    vector_str = "[" + ",".join(str(v) for v in vector) + "]"

    # Step 3: Run cosine similarity search via Supabase RPC
    try:
        result = supabase.rpc("match_journals", {
            "query_embedding": vector_str,
            "match_count": body.limit * 4,  # over-fetch for post-filtering
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Database error: {e}")

    # Step 4: Post-filter and format results
    matches = []
    for row in result.data or []:
        # Quartile filter
        if body.min_quartile:
            row_rank = QUARTILE_RANK.get(row.get("quartile") or "", 99)
            min_rank = QUARTILE_RANK[body.min_quartile]
            if row_rank > min_rank:
                continue

        # APC filter
        if body.max_apc_usd is not None:
            apc = row.get("apc_amount_usd")
            if apc is not None and float(apc) > body.max_apc_usd:
                continue

        matches.append({
            **row,
            "similarity_score": round(float(row.get("similarity", 0)), 4),
            "match_reason": f"Strong match in {row.get('subject_area') or 'your field'}",
        })

        if len(matches) >= body.limit:
            break

    return matches


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}

@app.get("/debug")
async def debug():
    """Test if OpenAI and Supabase connections work."""
    # Test OpenAI
    try:
        emb = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input="test deepfake detection"
        )
        vector = emb.data[0].embedding
        vector_len = len(vector)
        vector_sample = vector[:3]
    except Exception as e:
        return {"error": f"OpenAI failed: {e}"}

    # Test Supabase RPC with string vector
    try:
        vector_str = "[" + ",".join(str(v) for v in vector) + "]"
        result = supabase.rpc("match_journals", {
            "query_embedding": vector_str,
            "match_count": 3,
        }).execute()
        top_result = result.data[0] if result.data else None
    except Exception as e:
        return {
            "openai": "ok",
            "vector_len": vector_len,
            "error": f"Supabase failed: {e}"
        }

    return {
        "openai": "ok",
        "vector_len": vector_len,
        "vector_sample": vector_sample,
        "supabase": "ok",
        "top_match": top_result.get("title") if top_result else None,
        "top_similarity": top_result.get("similarity") if top_result else None,
    }