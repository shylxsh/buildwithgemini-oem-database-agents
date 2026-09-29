# My agent: power-fetch
One-liner: A conversational agent that helps engineers and project managers discover, navigate, and query OEM project databases (TATA, SKODA, Mahindra, etc.) with a catalog of project collections (details, git, manifest).

Tool coverage:
- Memory: Active project context across turns (e.g., remember chosen OEM/project like Nexon or Kushaq); fallback to asking the user for missing details.
- Tools:
  - `list_projects`: Discover available projects and OEMs in the database.
  - `list_collections`: Discover collections within a project (`details`, `git`, `manifest`).
  - `fetch_record`: Fetch raw JSON records from `http://localhost:8000/projects/{project_id}/{collection_name}/{record}`.
  - `fuzzy_match_query`: Search and disambiguate queries across project records, tagging complex queries with explicit fuzzy matching notices.
- Catalog/UI: Available projects shown as clickable buttons/cards, and retrieved record details rendered as an A2UI final details card with endpoint link, summary, and raw JSON.
- Image gen: Optional OEM/project emblem/badge or architecture visualization.
- Sandbox: n/a

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Mock FastAPI database service, fuzzy matching router, custom A2UI cards for project manifests and git links.
