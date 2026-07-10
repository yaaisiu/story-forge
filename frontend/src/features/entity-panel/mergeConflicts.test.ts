// Tests for the pure merge-conflict mapper (Session 43 — M4.S3b-fe).
//
// Mirrors the backend's `detect_property_conflicts` (domain/entity_merge.py): a conflict is a
// key BOTH entities set to *different* values. A key only one side sets, or both set equally,
// is not a conflict — the server unions it silently, so we omit it. `resolvedPropertiesFrom`
// turns the author's per-key choice into the `resolved_properties` dict the merge route wants
// (only the conflict keys; a missing pick defaults to keeping the survivor's value).

import { describe, expect, it } from "vitest";

import { buildConflictRows, resolvedPropertiesFrom } from "./mergeConflicts";

describe("buildConflictRows", () => {
  it("returns no rows when the property sets do not collide", () => {
    expect(buildConflictRows({ age: 40 }, { role: "priestess" })).toEqual([]);
  });

  it("omits a key both sides set to the same value (server unions it)", () => {
    expect(buildConflictRows({ age: 40, role: "priestess" }, { role: "priestess" })).toEqual([]);
  });

  it("emits one row per key set to different values, carrying both values", () => {
    const rows = buildConflictRows({ age: 40, role: "priestess" }, { age: 41, home: "Oakhaven" });
    expect(rows).toEqual([{ key: "age", survivorValue: 40, absorbedValue: 41 }]);
  });

  it("treats deep-equal object/array values as non-conflicting regardless of key order", () => {
    const rows = buildConflictRows({ tags: { a: 1, b: 2 } }, { tags: { b: 2, a: 1 } });
    expect(rows).toEqual([]);
  });

  it("flags differing object values as a conflict", () => {
    const rows = buildConflictRows({ tags: { a: 1 } }, { tags: { a: 2 } });
    expect(rows).toEqual([{ key: "tags", survivorValue: { a: 1 }, absorbedValue: { a: 2 } }]);
  });
});

describe("resolvedPropertiesFrom", () => {
  const rows = [
    { key: "age", survivorValue: 40, absorbedValue: 41 },
    { key: "home", survivorValue: "Eldmerra", absorbedValue: "Oakhaven" },
  ];

  it("defaults to the survivor's value when a key is unpicked", () => {
    expect(resolvedPropertiesFrom(rows, {})).toEqual({ age: 40, home: "Eldmerra" });
  });

  it("keeps the chosen side per key", () => {
    expect(resolvedPropertiesFrom(rows, { age: "absorbed", home: "survivor" })).toEqual({
      age: 41,
      home: "Eldmerra",
    });
  });

  it("only carries the conflict keys (never unrelated properties)", () => {
    const resolved = resolvedPropertiesFrom(rows, { age: "survivor", home: "absorbed" });
    expect(Object.keys(resolved).sort()).toEqual(["age", "home"]);
    expect(resolved).toEqual({ age: 40, home: "Oakhaven" });
  });
});
