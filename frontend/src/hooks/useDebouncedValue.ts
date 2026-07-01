// Debounce a rapidly-changing value (Session 73, Graph-quality S2). The graph
// viewer's node-search box updates on every keystroke, but recomputing the
// match/focus set per character would jank a dense graph — so the search term is
// debounced before it drives the (imperative) cytoscape highlight/pan. Factored into
// a hook (not an inline effect) so the timing logic is unit-testable, per the
// "logic lives in hooks, not components" rule (frontend/src/AGENTS.md).

import { useEffect, useState } from "react";

/** The `value` echoed back, but only after it has held steady for `delayMs`. Each
 *  change restarts the timer, so a burst of updates yields just the final value. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
