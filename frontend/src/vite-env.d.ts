/// <reference types="vite/client" />
// Brings Vite's ambient module declarations into TS scope so side-effect imports
// of static assets (e.g. `import "./index.css"` in main.tsx for Tailwind) are
// understood by `tsc --noEmit`. Vite handles the actual transform; this file
// only teaches the typechecker that such imports are legal.
//
// Also augments `import.meta.env` with the project-specific VITE_* variables
// the app reads, so `tsc --noEmit` typechecks `import.meta.env.VITE_API_BASE_URL`
// instead of widening it to `any` from Vite's default index signature.

interface ImportMetaEnv {
  /** Backend base URL; defaults to `http://localhost:8000` when unset. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
