from fastapi import FastAPI, Request
import httpx

app = FastAPI()

SUPABASE_URL = "https://uafyaolgsepatpkgxrha.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVhZnlhb2xnc2VwYXRwa2d4cmhhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY5MTYwNDYsImV4cCI6MjA2MjQ5MjA0Nn0.heNSA8V86WSBXWWQSqzpLYS5p-v5TyKhSo-PB8XnT60"

@app.post("/api/receive")
async def receive(request: Request):
    body = await request.body()
    message = body.decode("utf-8").strip()

    if not message:
        return {"error": "No message provided"}

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/messages",
            headers={
                "apikey": SUPABASE_API_KEY,
                "Authorization": f"Bearer {SUPABASE_API_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            json={"message": message}
        )

    if res.status_code >= 400:
        return {"error": res.text}

    return {"status": "Message stored"}
