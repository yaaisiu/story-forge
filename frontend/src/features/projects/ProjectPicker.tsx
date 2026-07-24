// Project / story picker (Session 53 — M4 multi-story frontend, spec §3.4).
//
// The navigation hub multi-story needs: list every project (GET /projects), select
// one to list its stories (GET /projects/{id}/stories), and from there open a story's
// hub (Grzymalin S3 — the per-story landing page linking all its screens) — or add
// another story to the same project (which routes back to the upload screen carrying
// the project id, so the new story joins the shared graph).
//
// Components render and dispatch; the data lives in the query hooks (frontend/src/CLAUDE.md).
// Selection is local UI state. Dates are sliced to YYYY-MM-DD (the ISO prefix) to keep
// the readout deterministic and locale-independent — no time-of-day precision is needed.

import { useState } from "react";

import { Link } from "react-router-dom";

import { useProjects, type ProjectSummary } from "../../lib/api/useProjects";
import { useProjectStories } from "../../lib/api/useProjectStories";

function isoDate(value: string): string {
  return value.slice(0, 10);
}

export function ProjectPicker() {
  const projects = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const stories = useProjectStories(selectedProjectId ?? undefined);

  const selectedProject: ProjectSummary | null =
    projects.data?.find((p) => p.id === selectedProjectId) ?? null;

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Projects</h1>
          <p className="text-sm text-gray-600">
            Pick a project to see its stories, or start a new one. All stories in a project share
            one knowledge graph.
          </p>
        </div>
        <Link
          data-testid="upload-new-link"
          to="/"
          className="shrink-0 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Upload a new story
        </Link>
      </header>

      <div className="flex min-h-0 flex-1 gap-6">
        {/* Project list */}
        <section className="flex w-1/2 flex-col gap-2">
          <h2 className="text-sm font-medium text-gray-700">All projects</h2>
          {projects.isPending && (
            <p data-testid="projects-loading" className="text-sm text-gray-500">
              Loading projects…
            </p>
          )}
          {projects.isError && (
            <p data-testid="projects-error" role="alert" className="text-sm text-red-700">
              Couldn&rsquo;t load projects.
            </p>
          )}
          {projects.isSuccess && projects.data.length === 0 && (
            <p data-testid="projects-empty" className="text-sm text-gray-500">
              No projects yet. Upload a story to create one.
            </p>
          )}
          {projects.isSuccess &&
            projects.data.map((project) => (
              <button
                key={project.id}
                type="button"
                data-testid={`project-row-${project.id}`}
                aria-pressed={project.id === selectedProjectId}
                onClick={() => setSelectedProjectId(project.id)}
                className={
                  project.id === selectedProjectId
                    ? "rounded border border-blue-500 bg-blue-50 px-4 py-3 text-left"
                    : "rounded border border-gray-200 px-4 py-3 text-left hover:bg-gray-50"
                }
              >
                <span className="block font-medium text-gray-900">{project.name}</span>
                <span className="block text-xs text-gray-500">
                  {project.language} · {project.story_count} stor
                  {project.story_count === 1 ? "y" : "ies"} · {isoDate(project.created_at)}
                </span>
              </button>
            ))}
        </section>

        {/* Stories of the selected project */}
        <section className="flex w-1/2 flex-col gap-2">
          {!selectedProject && (
            <p data-testid="stories-placeholder" className="text-sm text-gray-500">
              Select a project to see its stories.
            </p>
          )}
          {selectedProject && (
            <>
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-medium text-gray-700">
                  Stories in {selectedProject.name}
                </h2>
                <Link
                  data-testid="add-story-link"
                  to={`/?project_id=${selectedProject.id}&project_name=${encodeURIComponent(
                    selectedProject.name,
                  )}`}
                  className="shrink-0 rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  + Add a story
                </Link>
              </div>
              {stories.isPending && (
                <p data-testid="stories-loading" className="text-sm text-gray-500">
                  Loading stories…
                </p>
              )}
              {stories.isError && (
                <p data-testid="stories-error" role="alert" className="text-sm text-red-700">
                  Couldn&rsquo;t load this project&rsquo;s stories.
                </p>
              )}
              {stories.isSuccess && stories.data.length === 0 && (
                <p data-testid="stories-empty" className="text-sm text-gray-500">
                  This project has no stories yet.
                </p>
              )}
              {stories.isSuccess &&
                stories.data.map((story) => (
                  // The row opens the story's hub (S3), from which every screen
                  // (structure/reader/graph/review/relations/duplicates/normalise-names)
                  // is one click — so the picker no longer needs per-screen quick-links.
                  <Link
                    key={story.id}
                    data-testid={`story-row-${story.id}`}
                    to={`/stories/${story.id}`}
                    className="flex items-center justify-between gap-2 rounded border border-gray-200 px-4 py-3 hover:border-blue-400 hover:bg-gray-50"
                  >
                    <div className="min-w-0">
                      <span className="block truncate font-medium text-gray-900">
                        {story.title}
                      </span>
                      <span className="block text-xs text-gray-500">
                        {isoDate(story.ingested_at)}
                      </span>
                    </div>
                    <span className="shrink-0 text-sm font-medium text-blue-600">Open →</span>
                  </Link>
                ))}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
