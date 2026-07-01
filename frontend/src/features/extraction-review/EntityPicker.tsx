// Manual-handpick entity picker (M3.S4d — Stage 4 review, spec §3.3 *Manual handpick*).
//
// The reviewer's escape hatch when a true duplicate slipped past the cascade's top-3
// alternatives: search ALL of the project's accepted entities and pick any one as the merge
// target. Owns its search box (local UI state) and reads ranked hits via `useEntitySearch`
// (TanStack server state — no useEffect(fetch)); dispatches the chosen entity up via
// `onPick`. The box is a real <input>, so ReviewQueue's window keyboard scheme leaves it
// alone (isEditableTarget) — typing a search never triggers J/K/A/N/M/R.

import { useState } from "react";

import { useEntitySearch, type EntitySearchResult } from "../../lib/api/useEntitySearch";

interface EntityPickerProps {
  storyId: string | undefined;
  /** Commit a searched entity as the merge target. */
  onPick: (result: EntitySearchResult) => void;
  /** A decision is in flight — disable the search and its results. */
  disabled?: boolean;
}

export function EntityPicker({ storyId, onPick, disabled = false }: EntityPickerProps) {
  const [query, setQuery] = useState("");
  const search = useEntitySearch(storyId, query);
  const results = search.data?.entities ?? [];

  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        Or search all entities
      </p>
      <input
        type="search"
        data-testid="entity-search-input"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        disabled={disabled}
        placeholder="Search the project’s entities to merge into…"
        className="w-full rounded border border-gray-200 px-2 py-1 text-xs"
      />
      {search.isError && (
        <p data-testid="entity-search-error" role="alert" className="text-xs text-red-700">
          Couldn&rsquo;t search entities. Please try again.
        </p>
      )}
      {results.length > 0 && (
        <ul data-testid="entity-search-results" className="flex flex-col gap-1">
          {results.map((result) => (
            <li key={result.entity_id}>
              <button
                type="button"
                data-testid="entity-search-result"
                onClick={() => onPick(result)}
                disabled={disabled}
                className="w-full rounded border border-gray-200 px-2 py-1 text-left text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {result.canonical_name}
                <span className="ml-1 text-gray-500">{result.type}</span>
                <span className="ml-1 text-gray-400">({result.score})</span>
                {result.aliases.length > 0 && (
                  <span data-testid="entity-search-aliases" className="ml-1 text-gray-400">
                    aka {result.aliases.join(", ")}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
