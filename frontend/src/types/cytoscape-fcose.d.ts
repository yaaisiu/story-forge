// Ambient declaration for `cytoscape-fcose` (Session 73, Graph-quality S2). The
// package ships no TypeScript types, so without this shim `import fcose from
// "cytoscape-fcose"` is an implicit `any` and fails strict `tsc`. A cytoscape layout
// extension is a registration function passed to `cytoscape.use`, so we type it as
// exactly that (an `Ext`), which is all we consume.

declare module "cytoscape-fcose" {
  import type { Ext } from "cytoscape";
  const fcose: Ext;
  export default fcose;
}
