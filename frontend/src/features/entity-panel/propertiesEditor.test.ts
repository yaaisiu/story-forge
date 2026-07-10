import { describe, expect, it } from "vitest";

import {
  isRowValueValid,
  rowsToProperties,
  toPropertyRows,
  type PropertyRow,
} from "./propertiesEditor";

// The typed `properties` editor (DM-S3a-5): the author edits an entity's free-form JSON
// `properties` as a list of key/value rows, each carrying a *kind* so a number stays a
// number on save (not stringified). Keys stay free (INV-4 — never a fixed schema). Nested
// objects/arrays are *preserved* through an edit (kind "json"), even though the PoC UI shows
// them read-only rather than offering a recursive editor. These tests encode that contract.

function row(key: string, value: string, kind: PropertyRow["kind"]): PropertyRow {
  return { key, value, kind };
}

describe("toPropertyRows", () => {
  it("infers a kind per value and renders an editable string", () => {
    const rows = toPropertyRows({ role: "priestess", age: 23, alive: true });
    expect(rows).toEqual([
      { key: "role", value: "priestess", kind: "string" },
      { key: "age", value: "23", kind: "number" },
      { key: "alive", value: "true", kind: "boolean" },
    ]);
  });

  it("treats nested objects, arrays, and null as preserved JSON", () => {
    const rows = toPropertyRows({
      titles: ["Warden", "Keeper"],
      home: { region: "Oakhaven" },
      heir: null,
    });
    expect(rows).toEqual([
      { key: "titles", value: '["Warden","Keeper"]', kind: "json" },
      { key: "home", value: '{"region":"Oakhaven"}', kind: "json" },
      { key: "heir", value: "null", kind: "json" },
    ]);
  });

  it("returns an empty list for empty properties", () => {
    expect(toPropertyRows({})).toEqual([]);
  });
});

describe("rowsToProperties", () => {
  it("coerces each kind back to its JSON type", () => {
    const rows = [
      row("role", "priestess", "string"),
      row("age", "23", "number"),
      row("alive", "true", "boolean"),
    ];
    expect(rowsToProperties(rows)).toEqual({ role: "priestess", age: 23, alive: true });
  });

  it("round-trips nested/array/null JSON values unchanged", () => {
    const original = { titles: ["Warden", "Keeper"], home: { region: "Oakhaven" }, heir: null };
    expect(rowsToProperties(toPropertyRows(original))).toEqual(original);
  });

  it("drops rows whose key is blank (after trim)", () => {
    const rows = [row("role", "priestess", "string"), row("   ", "orphan", "string")];
    expect(rowsToProperties(rows)).toEqual({ role: "priestess" });
  });

  it("trims keys and lets a later row overwrite an earlier duplicate key", () => {
    const rows = [row(" age ", "23", "number"), row("age", "40", "number")];
    expect(rowsToProperties(rows)).toEqual({ age: 40 });
  });
});

describe("isRowValueValid", () => {
  it("accepts a finite numeric string and rejects a non-numeric or blank one", () => {
    expect(isRowValueValid(row("age", "23", "number"))).toBe(true);
    expect(isRowValueValid(row("age", "old", "number"))).toBe(false);
    expect(isRowValueValid(row("age", "  ", "number"))).toBe(false);
  });

  it("accepts parseable JSON and rejects malformed JSON", () => {
    expect(isRowValueValid(row("titles", '["a","b"]', "json"))).toBe(true);
    expect(isRowValueValid(row("titles", "[oops", "json"))).toBe(false);
  });

  it("accepts any string or boolean value", () => {
    expect(isRowValueValid(row("role", "", "string"))).toBe(true);
    expect(isRowValueValid(row("alive", "true", "boolean"))).toBe(true);
  });
});
