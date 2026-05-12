# scripts/rebuild_index.py
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Get your DB connection string from:
# Supabase Dashboard → Settings → Database → Connection string → URI
# It looks like: postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres

DB_URL = "postgresql://postgres:[YOUR-PASSWORD]@db.wbiharsgqnayajqhmldt.supabase.co:5432/postgres"

print("Connecting to database...")
conn = psycopg2.connect(DB_URL)
conn.autocommit = True
cur = conn.cursor()

print("Dropping old index...")
cur.execute("DROP INDEX IF EXISTS idx_journals_embedding;")
print("Done.")

print("Building new HNSW index (this takes 2-3 minutes)...")
cur.execute("""
    CREATE INDEX idx_journals_embedding 
    ON journals USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
""")
print("Index rebuilt successfully.")

cur.close()
conn.close()