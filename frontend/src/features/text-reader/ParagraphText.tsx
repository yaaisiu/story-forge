// One paragraph of the reader, split into plain runs and highlighted <mark> spans
// (M4.S1, spec §3.5). Pure props (paragraph + entity catalog) so it renders without a
// query client or router — the container owns the data; this owns the rendering.
//
// The split is the pure `splitParagraph`; colour is `colorForType` (DM-IH-5). A mark's
// hover tooltip is the entity's canonical_name + type + aliases (DM-IH-8), pulled from
// the catalog. React escapes the text by default, so rendering author text + entity
// names into the DOM is safe (no dangerouslySetInnerHTML — see the proposal's Layer 7).

import { Fragment } from "react";

import type { ReaderEntity, ReaderParagraph } from "../../lib/api/useReader";
import { colorForType } from "./palette";
import { splitParagraph } from "./segments";

interface ParagraphTextProps {
  paragraph: ReaderParagraph;
  catalog: ReadonlyMap<string, ReaderEntity>;
}

/** Tooltip text for a highlight (DM-IH-8): "Name — type" + an aliases line if any. */
function tooltipText(entity: ReaderEntity): string {
  const head = `${entity.canonical_name} — ${entity.type}`;
  return entity.aliases.length > 0 ? `${head}\nAliases: ${entity.aliases.join(", ")}` : head;
}

export function ParagraphText({ paragraph, catalog }: ParagraphTextProps) {
  const segments = splitParagraph(paragraph.text, paragraph.highlights);

  return (
    <p data-testid="reader-paragraph" data-paragraph-id={paragraph.id} className="leading-relaxed">
      {segments.map((seg, i) => {
        if (seg.kind === "plain") return <Fragment key={i}>{seg.text}</Fragment>;

        const color = colorForType(seg.type);
        const entity = catalog.get(seg.entityId);
        return (
          <mark
            key={i}
            data-testid="highlight"
            data-entity-id={seg.entityId}
            data-entity-type={seg.type}
            title={entity ? tooltipText(entity) : seg.text}
            className="rounded-sm px-0.5"
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
