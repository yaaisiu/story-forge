// Unit test for the debounce hook (Session 73, Graph-quality S2). Fake timers so
// the delay is exercised deterministically without real waiting.

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 200));
    expect(result.current).toBe("a");
  });

  it("updates only after the delay elapses", () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 200), {
      initialProps: { v: "a" },
    });

    rerender({ v: "b" });
    expect(result.current).toBe("a"); // not yet

    act(() => vi.advanceTimersByTime(199));
    expect(result.current).toBe("a"); // still not

    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe("b"); // now
  });

  it("resets the timer on a rapid change (only the last value lands)", () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 200), {
      initialProps: { v: "a" },
    });

    rerender({ v: "b" });
    act(() => vi.advanceTimersByTime(150));
    rerender({ v: "c" });
    act(() => vi.advanceTimersByTime(150));
    expect(result.current).toBe("a"); // 'b' never settled — its timer was cleared

    act(() => vi.advanceTimersByTime(50));
    expect(result.current).toBe("c"); // 'c' settles 200ms after its own change
  });
});
