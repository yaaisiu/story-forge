/// <reference types="vite/client" />
// Brings Vite's ambient module declarations into TS scope so side-effect imports
// of static assets (e.g. `import "./index.css"` in main.tsx for Tailwind) are
// understood by `tsc --noEmit`. Vite handles the actual transform; this file
// only teaches the typechecker that such imports are legal.
