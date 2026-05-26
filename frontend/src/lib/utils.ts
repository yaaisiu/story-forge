// Frontend utility helpers. Currently a single function — `cn` — kept tiny on
// purpose. When the first shadcn primitive is hand-vendored (per the Session 6
// "B-now / A-when-needed" Decided), it imports `cn` from here, which is the
// canonical shadcn location. Standing in for `clsx + tailwind-merge` with the
// minimum that earns its place; swap in those libs only when an actual primitive
// needs `tailwind-merge`'s conflict resolution (e.g. variant overrides).

/**
 * Compose class names from strings and conditional values. Falsy values
 * (`false`, `null`, `undefined`, `""`) are dropped; truthy strings are joined
 * with a single space. Use this in place of `"a b " + (cond ? "x" : "y")`
 * patterns so the conditional reads obviously and an extra space doesn't sneak
 * in. Not a `clsx` replacement — we don't take objects-keyed-by-class or arrays
 * because we don't need them yet.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
