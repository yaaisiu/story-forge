// Tests for the manual-handpick entity picker (M3.S4d — Stage 4 review).
//
// The picker owns a search box (local UI state) and reads ranked hits via useEntitySearch;
// it dispatches the chosen entity up via onPick. These mock the hook so the picker's own
// behaviour — search box drives the query, results render, clicking a result picks it — is
// tested without a network. The hook itself is covered by useEntitySearch.test.tsx.

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EntityPicker } from "./EntityPicker";
import { useEntitySearch } from "../../lib/api/useEntitySearch";

vi.mock("../../lib/api/useEntitySearch", () => ({
  useEntitySearch: vi.fn(),
}));

const mockedUseEntitySearch = vi.mocked(useEntitySearch);

function stubSearch(over: Record<string, unknown> = {}) {
  mockedUseEntitySearch.mockReturnValue({
    data: { entities: [] },
    isError: false,
    ...over,
  } as unknown as ReturnType<typeof useEntitySearch>);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("EntityPicker", () => {
  it("drives useEntitySearch with the story id and the typed query", () => {
    stubSearch();
    render(<EntityPicker storyId="s1" onPick={vi.fn()} />);

    fireEvent.change(screen.getByTestId("entity-search-input"), { target: { value: "Kat" } });

    expect(mockedUseEntitySearch).toHaveBeenLastCalledWith("s1", "Kat");
  });

  it("renders the ranked hits and picks one on click", () => {
    const onPick = vi.fn();
    stubSearch({
      data: {
        entities: [
          {
            entity_id: "e-kat",
            canonical_name: "Katarzyna",
            type: "Character",
            score: 42,
            aliases: [],
          },
        ],
      },
    });
    render(<EntityPicker storyId="s1" onPick={onPick} />);

    const result = screen.getByTestId("entity-search-result");
    expect(result).toHaveTextContent("Katarzyna");
    fireEvent.click(result);

    expect(onPick).toHaveBeenCalledWith({
      entity_id: "e-kat",
      canonical_name: "Katarzyna",
      type: "Character",
      score: 42,
      aliases: [],
    });
  });

  it("surfaces a search error", () => {
    stubSearch({ data: undefined, isError: true });
    render(<EntityPicker storyId="s1" onPick={vi.fn()} />);
    expect(screen.getByTestId("entity-search-error")).toBeInTheDocument();
  });
});
