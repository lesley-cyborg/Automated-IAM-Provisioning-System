import hmac
import hashlib
import os
import json

# Use the same secret from your .env file
SECRET = os.getenv("HR_WEBHOOK_SECRET", "dev-secret-change-me")

payload = {
    "event_type": "user_hired",
    "email": "sam.lee@company.com",
    "full_name": "Sam Lee",
    "department": "Security"
}

# IMPORTANT: json.dumps must match exactly how FastAPI receives it (no extra spaces)
body = json.dumps(payload, separators=(",", ":"))

# Generate HMAC-SHA256
signature = hmac.new(
    SECRET.encode(), 
    body.encode(), 
    hashlib.sha256
).hexdigest()

print("\n--- COPY THIS CURL COMMAND ---")
print(f"curl.exe -X POST http://127.0.0.1:8000/api/v1/webhooks/hr-event ^")
print(f"  -H \"Content-Type: application/json\" ^")
print(f"  -H \"x-hr-signature: {signature}\" ^")
print(f"  -d '{body}'")
print("------------------------------\n")