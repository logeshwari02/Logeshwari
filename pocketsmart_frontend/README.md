# PocketSmart AI — Frontend

This folder contains the frontend requested by the PocketSmart AI project brief. The source document describes a lightweight, responsive frontend using HTML/CSS/Jinja2, individual planner forms connected to FastAPI POST routes, card-style AI recommendation output, authentication/session personalization, testimonials, dashboard, and recommendation history. The frontend here keeps those page categories and connects them to the FastAPI backend.

## Pages included

- `index.html` — Home / landing page
- `testimonials.html` — Testimonials page
- `register.html` — Register page
- `login.html` — Login page
- `dashboard.html` — User dashboard
- `home_planner.html` — Home Interior Budget Planner
- `home_recommendations.html` — Home Interior Recommendations
- `party_planner.html` — Party Budget Planner
- `party_recommendations.html` — Party Budget Recommendations
- `jewelry_planner.html` — Jewelry Budget Planner (optional outfit image)
- `jewelry_recommendations.html` — Jewelry Budget Recommendations
- `history.html` — Recommendation History

## Backend integration

By default the frontend calls:

`http://127.0.0.1:8000`

The JavaScript expects these FastAPI routes:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /session-info`
- `GET /session-data`
- `GET /history`
- `POST /planners/home`
- `POST /planners/party`
- `POST /planners/jewelry`
- `POST /planners/jewelry-upload`

The frontend stores the JWT in `localStorage` and sends it as a Bearer token on protected requests.

## Run locally

Because browser JavaScript needs an HTTP origin for API calls, serve this folder on an HTTP port rather than opening the HTML files directly.

From the `pocketsmart_frontend` folder:

```powershell
python -m http.server 5173
```

Then open:

`http://127.0.0.1:5173/`

The root `index.html` redirects to the Home page automatically. You can also run `run_frontend.bat` by double-clicking it.

The backend should be running on `http://127.0.0.1:8000`.

The project backend's default CORS settings include port 5173, so this matches the documented development setup.

## Optional API base override

Before loading the page, you can set a custom base URL in the browser console:

```js
localStorage.setItem('pocketsmart_api_base', 'http://127.0.0.1:8000')
```

Reload the page afterwards.

## Notes

The project brief identifies testimonials as a required frontend page but does not provide actual testimonial text. Therefore the testimonials page contains clearly marked placeholders instead of fabricated customer reviews.
