// Live-preview outline parser for the manual-mode editor (Session 6).
//
// A TS mirror of `backend/src/story_forge/domain/chunking.parse_manual_outline`.
// The backend re-parses the same text on submit, so the two implementations
// MUST agree on what becomes a chapter / scene / paragraph. The algorithm is
// trivial enough that drift risk is low; the unit tests next to this file pin
// the rules. Auto/hybrid modes don't use this parser — they go straight to the
// backend and render the persisted tree.

export interface OutlineScene {
  title: string | null;
  paragraphs: string[];
}

export interface OutlineChapter {
  title: string | null;
  scenes: OutlineScene[];
}

export interface Outline {
  chapters: OutlineChapter[];
}

export interface OutlineCounts {
  chapters: number;
  scenes: number;
  paragraphs: number;
}

// CommonMark requires the space after the hashes — "###Dawn" is body text, not
// a heading. Matches `^(#{1,3})[ \t]+(.*)$` from the backend.
const HEADING = /^(#{1,3})[ \t]+(.*)$/;
// A paragraph-block separator is one-or-more blank lines, with possible whitespace.
const BLANK_LINE = /\n[ \t]*\n+/;

function splitParagraphs(text: string): string[] {
  return text
    .split(BLANK_LINE)
    .map((block) => block.trim())
    .filter((block) => block.length > 0);
}

export function parseManualOutline(rawText: string): Outline {
  const text = rawText.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const outline: Outline = { chapters: [] };
  let buffer: string[] = [];

  function currentChapter(): OutlineChapter {
    let last = outline.chapters.at(-1);
    if (last === undefined) {
      last = { title: null, scenes: [] };
      outline.chapters.push(last);
    }
    return last;
  }

  function currentScene(): OutlineScene {
    const chapter = currentChapter();
    let last = chapter.scenes.at(-1);
    if (last === undefined) {
      last = { title: null, paragraphs: [] };
      chapter.scenes.push(last);
    }
    return last;
  }

  function flush(): void {
    const paragraphs = splitParagraphs(buffer.join("\n"));
    buffer = [];
    if (paragraphs.length > 0) {
      currentScene().paragraphs.push(...paragraphs);
    }
  }

  for (const line of text.split("\n")) {
    const match = HEADING.exec(line);
    if (match === null) {
      buffer.push(line);
      continue;
    }
    // Capturing groups 1 and 2 are guaranteed to exist when `exec` returns a
    // match against this regex. Bind to `string` so the rest of the loop body
    // can use them without optional-chaining gymnastics.
    const hashes = match[1] as string;
    const title = (match[2] as string).trim();
    if (hashes === "#") {
      // Story title — not a structural boundary; drop the marker line.
      continue;
    }
    flush();
    if (hashes === "##") {
      outline.chapters.push({ title: title || null, scenes: [] });
    } else {
      currentChapter().scenes.push({ title: title || null, paragraphs: [] });
    }
  }
  flush();
  return outline;
}

export function countOutline(outline: Outline): OutlineCounts {
  let scenes = 0;
  let paragraphs = 0;
  for (const chapter of outline.chapters) {
    scenes += chapter.scenes.length;
    for (const scene of chapter.scenes) {
      paragraphs += scene.paragraphs.length;
    }
  }
  return { chapters: outline.chapters.length, scenes, paragraphs };
}
