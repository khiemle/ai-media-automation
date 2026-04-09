# AI Media Automation — Copilot Instructions

## Project Reality

- This repository contains two related systems:
  - the core automation pipeline in `database/`, `scraper/`, `vector_db/`, `rag/`, `pipeline/`, `uploader/`, `feedback/`, `daily_pipeline.py`, and `batch_runner.py`
  - the management console in `console/`
- The planning documents describe the intended end state, but the current codebase is not fully integrated yet.
- Treat `CLAUDE.md`, `01_product_spec.md`, `02_architecture_design.md`, `03_implementation_plan.md`, and `05_core_pipeline_implementation_plan.md` as design and roadmap context, not proof that every feature is already wired.
- When docs and code disagree, prefer the current code and recent runtime behavior.
- The console tool does not fully integrate with the core pipeline yet. Implement integrations incrementally and verify each boundary explicitly.

## Primary Goal

- Build the management console as a thin control layer over the existing core pipeline.
- Do not redesign or replace the pipeline architecture just to make the console easier.
- Preserve shared DB and filesystem integration points.
- Prefer minimal, vertical slices that move a specific console feature from stubbed to real.

## Architecture Rules

- Keep the console in `console/` and the core pipeline outside it.
- Prefer these call patterns from console code:
  - direct imports for lightweight reads and business logic
  - Celery tasks for operations expected to take more than 5 seconds
  - subprocess only for external tools such as `ffmpeg`, `ffprobe`, `pg_isready`, `nvidia-smi`, or CLI-bound workflows
- Keep PostgreSQL as the shared source of truth.
- Keep ChromaDB as a separate vector store, not a replacement for relational data.
- Do not introduce a second backend stack or a second queue system.

## Current Development Priorities

- The current roadmap is split across two tracks:
  - console implementation work in `03_implementation_plan.md`
  - core pipeline implementation and console integration work in `05_core_pipeline_implementation_plan.md`
- For console work, prioritize features that replace stubs and mock data with real backend/API flows.
- For integration work, wire the console to existing pipeline modules without changing public behavior unless required.
- Prefer shipping one working module at a time in this order unless the task says otherwise:
  - scraper
  - scripts
  - production
  - pipeline monitoring
  - uploads
  - performance/system

## Backend Guidance

- Backend stack is FastAPI + SQLAlchemy + Celery + Redis.
- Run FastAPI from the repository root, not from `console/`.
- Run Alembic from `console/backend/`.
- Heavy actions should return quickly with a `task_id` and continue in Celery.
- Audit every write operation that changes editor-visible state.
- Encrypt OAuth secrets at rest using Fernet.
- Respect role boundaries:
  - `admin` can access all modules
  - `editor` must not be given system, LLM, or credential-management capabilities beyond the documented scope
- When adding service logic, keep routers thin and place business rules in `console/backend/services/`.
- When integrating with pipeline modules, validate exact function signatures in code before calling them.

## Frontend Guidance

- Frontend stack is React 18 + Vite + Tailwind in `console/frontend/`.
- Use `ai_media_console.jsx` as the visual and interaction reference for the console UX.
- Reuse the prototype's product language and information architecture:
  - 8 main tabs
  - dense operational dashboards
  - IBM Plex typography
  - dark, data-heavy control-room aesthetic
  - compact cards, badges, progress bars, tables, modals, and timeline views
- Do not build a generic SaaS dashboard. The UI should feel like an operator console.
- Match established console behavior before inventing new flows.
- Prefer existing frontend structure:
  - pages in `console/frontend/src/pages/`
  - shared UI in `console/frontend/src/components/`
  - API calls in `console/frontend/src/api/`
  - hooks in `console/frontend/src/hooks/`
- Keep JWT in memory only. Never add `localStorage` or `sessionStorage` token persistence.

## Data and Workflow Expectations

- The core user workflow is:
  - inspect scraped trend data
  - generate scripts from curated context
  - edit and approve scripts
  - produce video assets and final renders
  - assign upload targets and publish
  - monitor performance and system health
- Preserve script lifecycle semantics:
  - `draft -> pending_review -> approved -> producing -> completed`
  - rejected scripts return to `draft`
  - edited approved scripts may enter `editing` and return to `approved`
- Preserve template-driven behavior for uploads, channels, and production defaults.

## Code Change Strategy

- Prefer root-cause fixes over UI-only patches.
- Do not silently rely on placeholder data if a real integration is expected.
- If a feature is still stubbed, either:
  - wire it to the real module end to end, or
  - keep the stub explicit and document the missing integration clearly
- Avoid broad rewrites. Keep changes scoped to the feature being integrated.
- Do not change core pipeline semantics unless the task explicitly requires pipeline work.
- If touching shared boundaries between console and core, verify both sides after the change.

## Verification Expectations

- After backend changes, verify with targeted commands or endpoint-level checks.
- After frontend changes, verify the affected flow in the existing app structure and keep desktop layout usable at the control-console density shown in `ai_media_console.jsx`.
- For integration work, verify one real path end to end whenever possible.
- If a command or flow cannot be fully verified because of missing credentials, quotas, or external services, say so explicitly and separate that from repo-side issues.

## Safe Assumptions

- Shared DB tables for console and pipeline are intentional.
- Celery queues are part of the intended architecture, not incidental plumbing.
- The console should remain API-first and should not call pipeline code directly from the browser.
- The design documents are useful context, but implementation should follow the repo's actual state and active migration path.