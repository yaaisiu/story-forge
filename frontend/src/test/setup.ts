// vitest setup — registers @testing-library/jest-dom matchers (toBeInTheDocument, etc.)
// so component tests can assert on rendered DOM with the conventional matchers,
// and unmounts any rendered component after each test so multiple `render(...)`
// calls in the same file don't share a DOM (the cause of "found multiple
// elements by ...testid" errors when running ≥2 tests against the same screen).
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

afterEach(() => {
  cleanup();
});
