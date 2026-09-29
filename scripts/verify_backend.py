"""Run lightweight local checks for PocketSmart without calling the Gemini API."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/verify_pocketsmart.db")
os.environ.setdefault("SECRET_KEY", "verify-secret-key-for-pocketsmart")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("DEBUG", "false")

try:
    from fastapi.testclient import TestClient
    from app.database import Base, engine
    from app.main import app
except Exception as exc:
    print(f"IMPORT FAILED: {type(exc).__name__}: {exc}")
    sys.exit(1)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

with TestClient(app) as client:
    checks = []

    r = client.get("/health")
    checks.append(("health", r.status_code == 200))

    reg = client.post(
        "/auth/register",
        json={"full_name": "Verification User", "email": "verify@example.com", "password": "strongpassword123"},
    )
    checks.append(("register", reg.status_code == 201))

    login = client.post(
        "/auth/login",
        json={"email": "verify@example.com", "password": "strongpassword123"},
    )
    checks.append(("login", login.status_code == 200))
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    home = client.post(
        "/planners/home",
        json={
            "budget": 50000,
            "rooms": ["Living Room"],
            "items": [{"name": "Sofa", "quantity": 1}],
        },
        headers=headers,
    )
    checks.append(("home planner", home.status_code == 200 and home.json()["ai_used"] is False))

    party = client.post(
        "/planners/party",
        json={"budget": 20000, "guest_count": 30, "event_type": "Birthday"},
        headers=headers,
    )
    checks.append(("party planner", party.status_code == 200))

    jewelry = client.post(
        "/planners/jewelry",
        json={"budget": 10000, "occasion": "Wedding"},
        headers=headers,
    )
    checks.append(("jewelry planner", jewelry.status_code == 200))

    history = client.get("/history", headers=headers)
    checks.append(("history", history.status_code == 200 and history.json()["total"] == 3))

    bad = client.get("/auth/me", headers=headers)
    checks.append(("protected route", bad.status_code == 200))

for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")

if not all(ok for _, ok in checks):
    sys.exit(1)

print(f"All {len(checks)} verification checks passed.")
