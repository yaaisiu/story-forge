import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Legend } from "./Legend";

describe("Legend", () => {
  it("renders a labelled swatch per entry", () => {
    render(
      <Legend
        entries={[
          { type: "character", color: "#2563eb" },
          { type: "place", color: "#16a34a" },
        ]}
      />,
    );
    const legend = screen.getByTestId("reader-legend");
    expect(legend).toHaveTextContent("character");
    expect(legend).toHaveTextContent("place");
  });

  it("renders nothing when there are no entries", () => {
    render(<Legend entries={[]} />);
    expect(screen.queryByTestId("reader-legend")).toBeNull();
  });
});
