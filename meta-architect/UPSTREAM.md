# Upstream provenance — this is a vendored copy

This `meta-architect/` directory is a **vendored copy** of a plugin that has **graduated** to its
own distributable home. Story Forge keeps this local copy and consumes it in-place; it does **not**
auto-install from upstream.

| | |
|---|---|
| **Upstream repo** | https://github.com/yaaisiu/claude-dev-tooling |
| **Upstream marketplace** | `claude-dev-tooling` (root `.claude-plugin/marketplace.json`) |
| **Plugin** | `meta-architect` |
| **Vendored version** | `0.1.0` |
| **Graduated / vendored on** | 2026-07-13 |

## Why vendored rather than marketplace-installed

The canonical `meta-architect` will be generalized for *any* workflow (alongside a future
`dev-rituals` plugin in the same monorepo). Story Forge is this tooling's most demanding user and
carries SF-specific tuning, so letting upstream changes flow in automatically risks breaking the
repo. We therefore keep an in-repo copy and **re-sync deliberately**, never by an automatic pull.
See `docs/decisions/0002-incubate-meta-architect-in-repo.md` for the incubation-and-graduation
record, and the design note `docs/design/tooling-extraction.md` §7 for the consumption model.

## How to re-sync (a deliberate act)

1. Review what changed upstream since the vendored version above.
2. Copy the updated plugin files into this directory, keeping SF-specific adaptations.
3. Bump the **Vendored version** + date in this file.
4. Land it as a normal reviewed PR.

This copy is wired for local use via `.claude/settings.json`
(`extraKnownMarketplaces.meta-architect-local` → the `./meta-architect` directory marketplace,
which reads `.claude-plugin/marketplace.json` here) + `enabledPlugins`.
