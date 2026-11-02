# AirTrip web client

Vue 3 + Vite + TypeScript + Tailwind 4 + Pinia single-page app for the AirTrip
API. It is served by Flask at `/app/` (Swagger stays at `/docs`), so there is no
separate frontend server in production.

## Run

```bash
# 1. the API (from the repository root)
.venv/bin/python airtrip_api.py        # http://127.0.0.1:5000

# 2. the client in dev mode
npm install
npm run dev                            # http://127.0.0.1:5173/app/
```

The dev server proxies `/api` to `127.0.0.1:5000`, so the JWT flow works
unchanged while you iterate. For the production bundle:

```bash
npm run build                          # writes dist/, Flask serves it at /app/
```

Sign in with `admin` / `admin` (or `user` / `user`). Dataset import lives at
`/app/import` and needs the admin account.

## Screens

| Route | Screen |
| --- | --- |
| `/login` | Sign in |
| `/dashboard` | Counts, quick actions, recent airports, last import |
| `/airports`, `/airports/:iata` | Airport list; detail with routes / airlines / destinations |
| `/airlines`, `/airlines/:iata` | Airline list; detail with that airline's routes |
| `/routes` | Route explorer with a detail drawer |
| `/plans`, `/plans/new`, `/plans/:id/edit` | Private plans, route picker, JSON/PNG export |
| `/users`, `/import` | Admin only: accounts and CSV import |
| `/style-tile` | Living style guide for the design system |

## Screenshots

| | |
| --- | --- |
| ![Dashboard](docs/app/dashboard.webp) | ![Airports](docs/app/airports.webp) |
| ![Airport detail](docs/app/airport-detail.webp) | ![Routes](docs/app/routes.webp) |
| ![Travel plans](docs/app/plans.webp) | ![Plan editor](docs/app/plan-editor.webp) |
| ![Accounts](docs/app/users.webp) | ![Import](docs/app/import.webp) |

The design system itself is documented in
[`docs/style-tile-desktop.webp`](docs/style-tile-desktop.webp); the live version
is `/app/style-tile`.

## Structure

```
src/
  api/          client.ts (fetch wrapper, JWT, blob downloads) + types.ts (Swagger shapes)
  components/   AeroWindow / AeroTable / AeroPager / AeroDialog / AeroDrawer / AeroIcon …
  layouts/      AppShell.vue — sidebar + content frame
  pages/        one file per screen
  stores/       auth.ts (token + account), toast.ts
  styles/       aero.css — the whole design system (tokens + components)
  router.ts     routes and the auth/admin guards
```

## Design system

`src/styles/aero.css` is the single source of truth: sky tokens, the glass pane
(`.win` + `.win-dense` for data-heavy panels), stamped buttons (`.btn`), fields,
badges, tables and the animated background scene (`App.vue`). Everything is CSS
and hand-drawn SVG — no wallpapers, icon packs or web fonts, so nothing is
licensed from anyone else.

Two rules worth keeping while adding screens:

- A glass pane needs something behind it. Blur over a flat gradient is
  indistinguishable from no blur; the background scene deliberately carries sun,
  shafts, glare discs and hard-edged hills for the panes to distort.
- Reflections and gloss are for tier-one objects (the hero orb, counter tiles,
  primary buttons). Data grids stay dense and quiet.

## Notes

- The API returns `{ items, page, page_size, total, pages }` envelopes; list
  screens keep their own filter + page state and debounce text input by ~220 ms.
- Export is account-wide (`/api/plans/export`), not per plan — the API has no
  per-plan export endpoint.
- Date inputs use the native picker, so their placeholder follows the browser
  locale; everything else in the UI is English.
