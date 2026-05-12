import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.environ.get("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("Set SUPABASE_DB_URL in your .env file or environment.\n"
                       "Format: postgresql://postgres:[PASSWORD]@db.wbiharsgqnayajqhmldt.supabase.co:5432/postgres")

print("Connecting to database...")
conn = psycopg2.connect(DB_URL)
conn.autocommit = True
cur = conn.cursor()

print("Dropping old index...")
cur.execute("DROP INDEX IF EXISTS idx_journals_embedding;")
print("Old index dropped.")

print("Building new HNSW index (this takes 2-3 minutes)...")
cur.execute("""
    CREATE INDEX idx_journals_embedding
    ON journals USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
""")
print("Index rebuilt successfully.")

cur.execute("SELECT COUNT(*) FROM journals WHERE embedding IS NOT NULL;")
count = cur.fetchone()[0]
print(f"Journals with embeddings: {count:,}")

cur.close()
conn.close()
