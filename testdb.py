import psycopg2

try:
    conn = psycopg2.connect(
        host="aws-0-eu-central-1.pooler.supabase.com",
        port=5432,
        database="postgres",
        user="postgres.jrztabndshlxbikbnzwu",
        password="dontrun4rmGodohsinner",
        sslmode="require"
    )
    print("✅ Connected to Supabase successfully!")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")