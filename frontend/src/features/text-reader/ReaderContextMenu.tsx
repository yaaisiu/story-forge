// The reader's right-click correction menu (M4.S3c-fe2, spec §3.5).
//
// A positioned menu whose items depend on what the right-click landed on (`request.target`):
// a highlight offers the three §3.5 corrections (+ re-assign), a free selection offers "tag as
// entity". Pure render-and-dispatch — it calls `onAction` with the chosen `CorrectionAction`;
// the container (`TextReader`) owns the mutation hooks and decides whether the action runs
// immediately (the one-click suppressions) or opens the picker / boundary mode. Dismisses on
// Escape or an outside click, like a native context menu.

import { useEffect, useRef } from "react";

import type { ContextMenuRequest, CorrectionAction } from "./correction";

interface ReaderContextMenuProps {
  request: ContextMenuRequest;
  onAction: (action: CorrectionAction) => void;
  onDismiss: () => void;
}

interface MenuItem {
  action: CorrectionAction;
  label: string;
}

const HIGHLIGHT_ITEMS: readonly MenuItem[] = [
  { action: "not-this", label: "Not this entity" },
  { action: "reassign", label: "Re-assign to…" },
  { action: "not-an-entity", label: "Not an entity" },
  { action: "change-boundaries", label: "Change boundaries" },
];

const SELECTION_ITEMS: readonly MenuItem[] = [{ action: "tag", label: "Tag as entity" }];

export function ReaderContextMenu({ request, onAction, onDismiss }: ReaderContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Dismiss on Escape or a click outside the menu (native-context-menu behaviour).
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onDismiss();
    }
    function onPointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) onDismiss();
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [onDismiss]);

  const items = request.target === "highlight" ? HIGHLIGHT_ITEMS : SELECTION_ITEMS;

  return (
    <div
      ref={menuRef}
      role="menu"
      data-testid="reader-context-menu"
      className="fixed z-50 min-w-44 rounded-md border border-gray-200 bg-white py-1 shadow-lg"
      style={{ top: request.anchor.y, left: request.anchor.x }}
    >
      {items.map((item) => (
        <button
          key={item.action}
          type="button"
          role="menuitem"
          data-testid={`context-${item.action}`}
          className="block w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
          onClick={() => onAction(item.action)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
