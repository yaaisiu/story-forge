# AGENTS.md — frontend/

This directory holds the React + TypeScript frontend, built with Vite.

## Conventions

- TypeScript strict mode on
- Format: prettier. Lint: eslint with typescript-eslint
- Tests: vitest (unit) + Playwright (e2e, later)
- Package manager: npm (no yarn/pnpm churn unless we decide otherwise)
- All dependency pins in `package.json` are exact versions, minimum 14 days old

## State management

- **Server state:** TanStack Query (`@tanstack/react-query`). All API calls go through it. No `useEffect(fetch...)` patterns.
- **Local UI state:** `useState` / `useReducer` when scoped to a component.
- **Cross-component client state:** Zustand stores in `src/stores/`. Keep them small and focused.

## API client

- Generated from the backend's OpenAPI spec. Don't hand-write fetch calls.
- See `src/lib/api/` for the generated client and thin wrappers.

## Component organization

- `src/components/ui/` — generic primitives (buttons, inputs). Likely shadcn/ui base.
- `src/features/<feature>/` — feature-scoped components, hooks, and stores
- `src/app/` — top-level routing and providers
- Pages and routes via React Router

## Running locally

```bash
cd frontend
npm install
npm run dev
```

Backend should be on `localhost:8000`. CORS is strict — if dev URL changes, update the backend too.

**Browser smoke walk — use `http://localhost:5173`, the allowlisted origin.** The backend
CORS allowlist (§6.7) is exactly four loopback origins (`localhost`/`127.0.0.1` × `5173`/`3000`).
Two gotchas that look like app bugs but aren't:

- If port 5173 is taken, Vite silently falls back to **5174** — _not_ in the allowlist, so every
  request fails CORS and the UI shows the generic "… failed. Please try again." (a thrown `fetch`,
  not a typed `ApiError`). Kill the stray Vite instance and use 5173; **don't** widen the §6.7
  allowlist for a port collision.
- Open the app at `localhost`, not `127.0.0.1`, unless you've confirmed which the backend served
  the `Access-Control-Allow-Origin` for — both name forms are allowlisted, but mixing them across
  tabs is a needless variable. (Session 17 smoke walk: 5174 + a `127.0.0.1` tab each tripped this.)
