// One paragraph of the reader, split into plain runs and highlighted <mark> spans
// (M4.S1, spec §3.5). Pure props (paragraph + entity catalog) so it renders without a
// query client or router — the container owns the data; this owns the rendering.
//
// The split is the pure `splitParagraph`; colour is `colorForType` (DM-IH-5). A mark's
// hover tooltip is the entity's canonical_name + type + aliases (DM-IH-8), pulled from
// the catalog. React escapes the text by default, so rendering author text + entity
// names into the DOM is safe (no dangerouslySetInnerHTML — see the proposal's Layer 7).
//
// M4.S2b: a highlight is now an interactive button — clicking it opens the entity side
// panel (`onEntityClick`). When an occurrence is drilled from the panel, the container
// passes `flashEntityId` for *this* paragraph so the matching marks pulse briefly,
// pointing the author at the source text (DM-SP-3).

import { Fragment, memo } from "react";

import type { ReaderEntity, ReaderParagraph } from "../../lib/api/useReader";
import { colorForType } from "./palette";
import { splitParagraph } from "./segments";

interface ParagraphTextProps {
  paragraph: ReaderParagraph;
  catalog: ReadonlyMap<string, ReaderEntity>;
  onEntityClick: (entityId: string) => void;
  /** Entity whose marks in *this* paragraph should flash (occurrence drill-down), or null. */
  flashEntityId?: string | null;
}

/** Tooltip text for a highlight (DM-IH-8): "Name — type" + an aliases line if any. */
function tooltipText(entity: ReaderEntity): string {
  const head = `${entity.canonical_name} — ${entity.type}`;
  return entity.aliases.length > 0 ? `${head}\nAliases: ${entity.aliases.join(", ")}` : head;
}

// Memoized: the container holds whole-story selection + flash state, so it re-renders on
// every click/flash; without memo each paragraph would re-run `splitParagraph` over its
// full text on every one of those. With memo (props are stable refs — `catalog`/
// `onEntityClick` memoized, `paragraph` from the query cache — and `flashEntityId` is null
// for every paragraph except the flashed one), only the (un)flashed paragraph re-renders.
function ParagraphTextComponent({
  paragraph,
  catalog,
  onEntityClick,
  flashEntityId,
}: ParagraphTextProps) {
  const segments = splitParagraph(paragraph.text, paragraph.highlights);

  return (
    <p data-testid="reader-paragraph" data-paragraph-id={paragraph.id} className="leading-relaxed">
      {segments.map((seg, i) => {
        if (seg.kind === "plain") return <Fragment key={i}>{seg.text}</Fragment>;

        const color = colorForType(seg.type);
        const entity = catalog.get(seg.entityId);
        const isFlashing = flashEntityId === seg.entityId;
        return (
          <mark
            key={i}
            data-testid="highlight"
            data-entity-id={seg.entityId}
            data-entity-type={seg.type}
            data-flash={isFlashing ? "true" : undefined}
            role="button"
            tabIndex={0}
            title={entity ? tooltipText(entity) : seg.text}
            onClick={() => onEntityClick(seg.entityId)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onEntityClick(seg.entityId);
              }
            }}
            className={`cursor-pointer rounded-sm px-0.5 ${
              isFlashing ? "animate-pulse ring-2 ring-offset-1" : ""
            }`}
            // Open-world types (INV-4) can't map to Tailwind classes — the colour is
            // computed per type, so it must be an inline style (see palette.ts).
            style={{ backgroundColor: `${color}1a`, borderBottom: `2px solid ${color}` }}
          >
            {seg.text}
          </mark>
        );
      })}
    </p>
  );
}

export const ParagraphText = memo(ParagraphTextComponent);
