# AirTrip — Airline Operations API

**English** · [简体中文](README.md)

A personal REST API for exploring airline operations data and building private
travel plans. It is a Flask application (Flask-RESTX for Swagger docs,
SQLAlchemy for persistence, Flask-JWT-Extended for auth) backed by a local
SQLite database that is created next to the code on first run.

## Features

- **Authentication & accounts** — JWT bearer tokens with an `admin` / `user`
  role split; admins create, list, deactivate and delete accounts. A
  deactivation takes effect immediately because the token is re-checked on
  every request.
- **CSV import** — upload `airports.csv`, `airlines.csv` and `routes.csv`
  (alone or together). Each file is validated cell by cell, then the merged
  result is checked for internal consistency and referential integrity.
  Replacing `routes` is rejected with `409` while an existing travel plan still
  references a route that would be removed, so user data never disappears
  silently.
- **Exploration** — paginated, filterable, case-insensitive search over
  airports, airlines and routes; airports/airlines expose their routes and a
  route detail embeds both endpoints.
- **Travel plans** — named, private collections of routes with a date range.
  Plans belong to exactly one account and are invisible to everybody else
  (including the admin).
- **Export** — a plan set is downloadable as a self-contained JSON attachment
  or rendered as an inline PNG timeline of upcoming trips.
- **Swagger UI** at `/docs` for trying every endpoint by hand.
- **Web client** at `/app` — a single-page app over the same API: a Frutiger-Aero
  styled network explorer (airports, airlines, routes), private travel plans with
  a route picker, account administration and CSV import.

## Project layout

| Path | Purpose |
| --- | --- |
| `airtrip_api.py` | The whole application: models, helpers, resources, Swagger models. |
| `airtrip_tests.py` | Black-box pytest suite that drives a running instance over HTTP. |
| `airlines.csv`, `airports.csv`, `routes.csv` | Sample dataset used by the importer. |
| `requirements.txt` | Dependencies. |
| `airtrip.db` | SQLite database, generated on first run. |
| `airtrip-web/` | Vue 3 + Vite + TypeScript single-page client (`dist/` is served by Flask). |

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python airtrip_api.py          # Swagger UI: http://127.0.0.1:5000/docs
```

The API also serves the web client at <http://127.0.0.1:5000/app/>. The built
bundle lives in `airtrip-web/dist`; rebuild it after changing the client:

```bash
cd airtrip-web
npm install
npm run build        # production bundle, served by Flask at /app/
npm run dev          # or: hot-reload dev server at http://127.0.0.1:5173/app/
```

Two accounts are seeded on first run: `admin` / `admin` and `user` / `user`.
Log in at `POST /api/auth/login`, click **Authorize** in Swagger, and paste the
token. Then import the dataset as the admin:

```bash
curl -X POST http://127.0.0.1:5000/api/import \
  -H "Authorization: Bearer <admin token>" \
  -F "airports=@airports.csv" \
  -F "airlines=@airlines.csv" \
  -F "routes=@routes.csv"
```

Set `AIRTRIP_JWT_SECRET` to a real secret before exposing the service anywhere —
the built-in default is a development placeholder only.

## Web client

| Route | Screen |
| --- | --- |
| `/app/login` | Sign in (seeded accounts below). |
| `/app/dashboard` | Counts, quick actions, recently added airports, last import. |
| `/app/airports`, `/app/airports/:iata` | Searchable list; airports expose routes, airlines and destinations. |
| `/app/airlines`, `/app/airlines/:iata` | Airline directory and the routes each one flies. |
| `/app/routes` | Route explorer with a detail drawer. |
| `/app/plans`, `/app/plans/new`, `/app/plans/:id/edit` | Private plans with a route picker and JSON/PNG export. |
| `/app/users`, `/app/import` | Admin: account management and CSV import. |

`/app/style-tile` is the living style guide for the design system.

## Tests

```bash
rm -f airtrip.db               # start from a clean database
python airtrip_api.py          # in one terminal
pytest airtrip_tests.py -v     # in another (47 tests)
```

The suite talks to the API over HTTP and never imports the application, so it
checks exactly what a client sees. Point it at another port with
`API_BASE_URL=http://127.0.0.1:5056`.

## API surface

`/api/auth` · `/api/users` · `/api/import` · `/api/airports` · `/api/airlines`
· `/api/routes` · `/api/plans` (including `/api/plans/export`)
