# PocketSmart AI — Complete FastAPI Backend

A clean, modular backend for the PocketSmart AI project described in the supplied specification.

## Features

- JWT authentication: register, login, logout, `/auth/me`
- OAuth2 password-token endpoint at `/auth/token` for Swagger/frontend compatibility
- Token revocation on logout
- Session metadata and user-specific recommendation history
- Home, Party, and Jewelry budget planners
- Gemini integration through Google's official `google-genai` Python SDK
- Structured Gemini responses using Pydantic
- Multimodal Jewelry planner with optional outfit image upload
- Deterministic fallback recommendations when Gemini is unavailable
- CORS configuration for a separate frontend
- SQLite persistence out of the box
- Swagger UI at `/docs`
- Compatibility paths from the project specification: `/generate-home`, `/generate-party`, `/generate-jewelry`

## Project structure

```text
bproject/
├── app/
│   ├── routes/
│   │   ├── auth.py
│   │   ├── health.py
│   │   ├── history.py
│   │   └── planners.py
│   ├── services/
│   │   ├── gemini.py
│   │   ├── history.py
│   │   ├── platforms.py
│   │   └── recommendations.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── data/
├── tests/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── main.py
├── requirements.txt
└── run.bat
```

## 1. Windows setup

PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and add your **new** Gemini API key. Do not commit `.env`.

```env
GEMINI_API_KEY=your_new_key_here
GEMINI_MODEL=gemini-3.8-flash
SECRET_KEY=put-a-long-random-secret-here
```

`CORS_ORIGINS` accepts either comma-separated values:

```env
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173
```

or a JSON array:

```env
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

## 2. Start the server

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health: http://127.0.0.1:8000/health

## 3. Authentication

### Register

`POST /auth/register`

```json
{
  "full_name": "Sujay Emmanuel",
  "email": "sujay@example.com",
  "password": "strongpassword123"
}
```

### Login

`POST /auth/login`

```json
{
  "email": "sujay@example.com",
  "password": "strongpassword123"
}
```

Use the returned JWT as:

```text
Authorization: Bearer <token>
```

### Swagger OAuth2 token form

`POST /auth/token`

Swagger's Authorize flow can use username=email and password=your-password.

### Logout

`POST /auth/logout`

The presented JWT is placed on the server-side revocation list.

## 4. Planner APIs

### Home

`POST /planners/home`

```json
{
  "budget": 100000,
  "rooms": ["Living Room", "Bedroom"],
  "items": [
    {"name": "Sofa", "quantity": 1, "preferred_style": "Modern"},
    {"name": "Ceiling Light", "quantity": 3, "preferred_style": "Minimal"}
  ],
  "city": "Chennai",
  "style": "Modern",
  "notes": "Easy maintenance preferred"
}
```

### Party

`POST /planners/party`

```json
{
  "budget": 50000,
  "guest_count": 100,
  "event_type": "Birthday",
  "venue": "Community Hall",
  "city": "Chennai",
  "food_preference": "Vegetarian",
  "decoration_style": "Elegant"
}
```

### Jewelry — JSON/text only

`POST /planners/jewelry`

```json
{
  "budget": 10000,
  "occasion": "Wedding",
  "style": "Elegant",
  "metal_preference": "Gold",
  "outfit_color": "Maroon"
}
```

### Jewelry — optional outfit image

`POST /planners/jewelry-upload`

Use `multipart/form-data`:

```text
budget=10000
occasion=Wedding
style=Elegant
metal_preference=Gold
outfit_color=Maroon
outfit_image=<JPEG/PNG/WEBP>
```

The project-specification compatibility route is:

`POST /generate-jewelry`

## 5. History and session

- `GET /history`
- `GET /recommendations-details`
- `GET /session-info`
- `GET /session-data`
- `GET /auth/me`

All are scoped to the authenticated user.

## 6. Gemini behavior

The backend uses Google's official `google-genai` SDK. The model is configurable through `GEMINI_MODEL`.

When a Gemini key is configured, the planner sends the user request to Gemini and asks for a structured Pydantic response. The Jewelry upload route sends the image as a multimodal Gemini input for a dedicated outfit-visual analysis step, then uses that structured visual context in a second Gemini call to generate the final jewelry recommendations.

When Gemini is not configured or an API request fails, the backend returns a deterministic budget-aware fallback rather than crashing. This keeps the frontend development workflow usable.

## 7. Important product-data note

The supplied project document mentions Amazon, Flipkart, IKEA, Swiggy, Zomato and OYO. This backend does not claim live prices, stock, ratings or availability from those services. It generates estimates and platform search URLs. Live catalog data should be added later through an approved API/integration.

## 8. Tests

After installation:

```powershell
pytest -q
```

The automated tests use the deterministic fallback mode and do not require a real Gemini key.

### 9. Jewelry image reliability

The Jewelry upload path now validates the uploaded file with Pillow, corrects EXIF orientation, normalizes JPEG/PNG/WEBP input to a compact JPEG, and sends a plain multimodal image-understanding request to Gemini. The image call intentionally does **not** use structured-output schema enforcement. Its JSON is parsed locally and then passed into the final structured recommendation call. Transient Gemini server/rate-limit/timeout errors are retried before falling back.

Optional settings:

```env
GEMINI_IMAGE_RETRIES=3
GEMINI_REQUEST_RETRIES=2
```
