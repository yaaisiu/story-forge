# CLAUDE.md — frontend/

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
