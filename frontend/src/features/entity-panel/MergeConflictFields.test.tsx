// Tests for the extracted merge-conflict resolver fieldset (Session 79 — Graph-quality S4b).

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MergeConflictFields } from "./MergeConflictFields";
import type { ConflictRow } from "./mergeConflicts";

const AGE: ConflictRow = { key: "age", survivorValue: 40, absorbedValue: 42 };
const HOME: ConflictRow = { key: "home", survivorValue: "Oakhaven", absorbedValue: "Rivertown" };
const CONFLICTS: ConflictRow[] = [AGE, HOME];

describe("MergeConflictFields", () => {
  it("renders nothing when there are no conflicts", () => {
    const { container } = render(
      <MergeConflictFields conflicts={[]} picks={{}} onChange={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a keep/use pair per conflict and reflects the current pick", () => {
    render(
      <MergeConflictFields
        conflicts={CONFLICTS}
        picks={{ home: "absorbed" }}
        onChange={() => {}}
      />,
    );
    expect(screen.getAllByTestId("merge-conflict")).toHaveLength(2);
    // Unpicked key defaults to the survivor; the picked key reflects "absorbed".
    const [ageKeep] = screen.getAllByTestId("merge-keep-survivor");
    expect(ageKeep).toHaveAttribute("aria-pressed", "true");
    const useButtons = screen.getAllByTestId("merge-keep-absorbed");
    expect(useButtons[1]).toHaveAttribute("aria-pressed", "true");
  });

  it("calls onChange with the key and the chosen side", () => {
    const onChange = vi.fn();
    render(<MergeConflictFields conflicts={[AGE]} picks={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("merge-keep-absorbed"));
    expect(onChange).toHaveBeenCalledWith("age", "absorbed");
  });
});
