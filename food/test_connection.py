from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print("Connecting to:", url)

try:
    supabase = create_client(url, key)
    print("✅ Client created successfully")

    response = supabase.table("users").select("*").limit(1).execute()

    print("✅ Connected to Supabase!")
    print(response.data)

except Exception as e:
    print("❌ Connection failed:")
    print(e)