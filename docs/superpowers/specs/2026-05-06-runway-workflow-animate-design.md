# Design: Runway Workflow-Based Animation

**Date:** 2026-05-06  
**Status:** Approved

---

## Problem

The existing "Animate with Runway" flow uses the old `api.runwayml.com/v1/tasks` endpoint (gen3-alpha model) with user-controlled `motion_intensity` and `duration` parameters. The new requirement is to route all image animation through published Runway **workflows** on `api.dev.runwayml.com`, which encapsulate the model and parameters internally. The first workflow type is `loop`; more types will be added over time.

---

## Goals

- Replace the old Runway tasks API path with a workflow-based path
- Support multiple video types (each mapped to a specific published workflow)
- Keep workflow configuration out of code — editable without a deploy
- Simplify the AnimateModal UI to prompt + video type only

---

## Non-goals

- Keeping the old gen3-alpha tasks API as a fallback
- A DB table or admin UI for managing workflow configs
- Supporting workflows with more than two inputs (prompt + image)

---

## Architecture

### Config file: `config/runway_workflows.yaml`

Single source of truth for video-type → workflow mapping. Adding a new video type requires only a new entry here — no code changes.

```yaml
video_types:
  loop:
    workflow_id: "45c6012f-6993-4c34-85bd-cea416b04598"
    prompt_node_id: "db5ddb6c-0d86-401e-b777-6f29d4782235"
    image_node_id: "baa36f58-ee4d-459f-b6ff-9f040db04319"
```

Each entry has exactly three fields: `workflow_id`, `prompt_node_id`, `image_node_id`. All future workflow types follow the same schema.

---

### Backend

#### `console/backend/services/runway_service.py` — full rewrite

Drop all gen3-alpha methods. Two methods only:

```python
class RunwayService:
    BASE = "https://api.dev.runwayml.com/v1"
    VERSION_HEADER = "2024-11-06"

    def submit_workflow(
        self,
        workflow_id: str,
        prompt_node_id: str,
        image_node_id: str,
        prompt: str,
        image_uri: str,
    ) -> str:
        """POST /workflows/{workflow_id} → returns invocation_id."""

    def poll_workflow_invocation(self, invocation_id: str) -> dict:
        """GET /workflow_invocations/{invocation_id}
        Returns {"status": "PENDING|RUNNING|SUCCEEDED|FAILED", "output_url": str|None}

        Note: the exact field path for the output video URL in Runway's workflow
        invocation response must be verified at implementation time by logging the
        raw SUCCEEDED response. Likely candidates: result["outputs"][0]["url"] or
        result["output"][0]. The service method normalises this to output_url.
        """
```

Headers include `Authorization: Bearer {api_key}` and `X-Runway-Version: 2024-11-06`.

Request body for `submit_workflow`:
```json
{
  "nodeOutputs": {
    "{prompt_node_id}": {"prompt": {"type": "primitive", "value": "{prompt}"}},
    "{image_node_id}": {"image": {"type": "image", "uri": "{image_uri}"}}
  }
}
```

#### `console/backend/tasks/runway_task.py` — replace task

Remove `animate_asset_task`. Add `animate_workflow_task`:

- Registered as `tasks.animate_workflow`
- Polls `poll_workflow_invocation` every 30s, times out at 10 minutes
- On `SUCCEEDED`: downloads output video from `output_url`, saves to `RUNWAY_OUTPUT_DIR/runway_{asset_id}.mp4`, sets `VideoAsset.runway_status = "ready"`, `VideoAsset.file_path = <saved path>`
- On `FAILED` or timeout: sets `VideoAsset.runway_status = "failed"`
- Network errors: `self.retry(countdown=30)`

#### `console/backend/routers/production.py` — update animate endpoint

`AnimateBody` schema changes:
- Remove: `motion_intensity: int`, `duration: int`
- Add: `video_type: str`

Endpoint logic:
1. Load `config/runway_workflows.yaml`
2. Look up `video_types[video_type]` — return 400 if unknown
3. Build `image_uri` from `PUBLIC_API_URL` env var: `{PUBLIC_API_URL}/api/production/assets/{asset_id}/stream`
4. Call `RunwayService().submit_workflow(...)` → get `invocation_id`
5. Create child `VideoAsset(source="runway", runway_status="pending", ...)`
6. Dispatch `animate_workflow_task.delay(child.id, invocation_id, output_filename)`
7. Return `{"asset_id": child.id, "task_id": task.id, "invocation_id": invocation_id}`

---

### Frontend

#### `VideoAssetsPage.jsx` — `AnimateModal`

Before:
- Prompt textarea
- Motion intensity slider (1–10)
- Duration select (5s / 10s)

After:
- Prompt textarea
- Video type dropdown — values sourced from a hardcoded `VIDEO_TYPES` constant (initially `["loop"]`). When new types are added to the YAML, add them here too.

#### `api/client.js` — `animateWithRunway`

Request body changes from `{ prompt, motion_intensity, duration }` to `{ prompt, video_type }`.

---

## Data Flow

```
User: AnimateModal → prompt + video_type → "Animate →"
  ↓
POST /api/production/assets/{id}/animate  { prompt, video_type }
  ↓
Load runway_workflows.yaml → get workflow_id, prompt_node_id, image_node_id
  ↓
RunwayService.submit_workflow(...) → invocation_id
  ↓
Create child VideoAsset (runway_status=pending)
  ↓
animate_workflow_task.delay(asset_id, invocation_id, filename)  [Celery]
  ↓
Poll GET /workflow_invocations/{invocation_id} every 30s
  ↓
SUCCEEDED → download video → save to disk → VideoAsset.runway_status = "ready"
FAILED / timeout → VideoAsset.runway_status = "failed"
```

---

## Files Changed

| File | Change |
|------|--------|
| `config/runway_workflows.yaml` | **New** — workflow config |
| `console/backend/services/runway_service.py` | **Rewrite** — drop gen3-alpha, add workflow methods |
| `console/backend/tasks/runway_task.py` | **Rewrite** — replace `animate_asset_task` with `animate_workflow_task` |
| `console/backend/routers/production.py` | **Update** — new body schema, load YAML, call new service |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | **Update** — simplify `AnimateModal` |
| `console/frontend/src/api/client.js` | **Update** — `animateWithRunway` body |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `RUNWAY_API_KEY` | Auth token — already in `.env` |
| `PUBLIC_API_URL` | Used to build image URI for Runway — already used by current code |
