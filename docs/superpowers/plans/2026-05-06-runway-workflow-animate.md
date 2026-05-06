# Runway Workflow-Based Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old Runway gen3-alpha tasks API with published workflow invocations, adding a `video_type` concept so each type maps to a specific Runway workflow.

**Architecture:** A new `config/runway_workflows.yaml` maps video type names to workflow IDs and node IDs. `RunwayService` is rewritten with two workflow-only methods. A new Celery task `animate_workflow_task` polls `/workflow_invocations/{id}`. The animate endpoint in `production.py` loads the YAML, resolves the workflow, and dispatches the task. The `AnimateModal` frontend simplifies to prompt + video type.

**Tech Stack:** Python `requests`, PyYAML, Celery, FastAPI, React 18

---

## File Map

| File | Change |
|------|--------|
| `config/runway_workflows.yaml` | **New** — workflow config |
| `console/backend/services/runway_service.py` | **Rewrite** — drop gen3-alpha, add `submit_workflow` + `poll_workflow_invocation` |
| `console/backend/tasks/runway_task.py` | **Rewrite** — replace `animate_asset_task` with `animate_workflow_task` |
| `console/backend/routers/production.py` | **Update** — new `AnimateBody` schema, YAML load, new task dispatch |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | **Update** — simplify `AnimateModal` |
| `console/frontend/src/api/client.js` | **Update** — `animateWithRunway` body |
| `tests/test_runway_service.py` | **New** — unit tests for `RunwayService` |

---

## Task 1: Create workflow config file

**Files:**
- Create: `config/runway_workflows.yaml`

- [ ] **Step 1: Create the config file**

```yaml
video_types:
  loop:
    workflow_id: "45c6012f-6993-4c34-85bd-cea416b04598"
    prompt_node_id: "db5ddb6c-0d86-401e-b777-6f29d4782235"
    image_node_id: "baa36f58-ee4d-459f-b6ff-9f040db04319"
```

- [ ] **Step 2: Verify PyYAML is available**

```bash
python3 -c "import yaml; d = yaml.safe_load(open('config/runway_workflows.yaml')); print(d)"
```

Expected output:
```
{'video_types': {'loop': {'workflow_id': '45c6012f-...', 'prompt_node_id': 'db5ddb6c-...', 'image_node_id': 'baa36f58-...'}}}
```

If `ModuleNotFoundError`: run `pip install pyyaml` (it should already be installed — PyYAML is a transitive dep of many packages).

- [ ] **Step 3: Commit**

```bash
git add config/runway_workflows.yaml
git commit -m "feat: add runway_workflows.yaml config for video type → workflow mapping"
```

---

## Task 2: Rewrite RunwayService

**Files:**
- Modify: `console/backend/services/runway_service.py` (full rewrite)
- Create: `tests/test_runway_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_runway_service.py`:

```python
from unittest.mock import patch, MagicMock


def test_submit_workflow_returns_invocation_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "inv-abc123"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.submit_workflow(
            workflow_id="wf-id",
            prompt_node_id="node-prompt",
            image_node_id="node-image",
            prompt="gentle rain",
            image_uri="https://example.com/img.jpg",
        )

    assert result == "inv-abc123"
    url = mock_post.call_args[0][0]
    assert "api.dev.runwayml.com" in url
    assert "workflows/wf-id" in url
    body = mock_post.call_args[1]["json"]
    assert "node-prompt" in body["nodeOutputs"]
    assert body["nodeOutputs"]["node-prompt"]["prompt"]["value"] == "gentle rain"
    assert body["nodeOutputs"]["node-image"]["image"]["uri"] == "https://example.com/img.jpg"


def test_submit_workflow_includes_version_header():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "inv-xyz"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        svc.submit_workflow("wf", "pn", "in", "prompt", "uri")

    headers = mock_post.call_args[1]["headers"]
    assert headers["X-Runway-Version"] == "2024-11-06"
    assert headers["Authorization"] == "Bearer test-key"


def test_poll_workflow_invocation_succeeded_with_outputs_list():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "SUCCEEDED",
        "outputs": [{"url": "https://cdn.runway.com/video.mp4"}],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "SUCCEEDED"
    assert result["output_url"] == "https://cdn.runway.com/video.mp4"


def test_poll_workflow_invocation_succeeded_with_output_string_list():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "SUCCEEDED",
        "output": ["https://cdn.runway.com/video.mp4"],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "SUCCEEDED"
    assert result["output_url"] == "https://cdn.runway.com/video.mp4"


def test_poll_workflow_invocation_running():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "RUNNING"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "RUNNING"
    assert result["output_url"] is None


def test_poll_workflow_invocation_failed():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "FAILED"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "FAILED"
    assert result["output_url"] is None


def test_poll_uses_workflow_invocations_endpoint():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "RUNNING"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        svc.poll_workflow_invocation("inv-abc123")

    url = mock_get.call_args[0][0]
    assert "workflow_invocations/inv-abc123" in url
    assert "api.dev.runwayml.com" in url
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -m pytest tests/test_runway_service.py -v
```

Expected: `ImportError` or `AttributeError` — `RunwayService` doesn't have the new methods yet.

- [ ] **Step 3: Rewrite runway_service.py**

Replace the entire file `console/backend/services/runway_service.py` with:

```python
"""Runway Workflow API client — submit and poll workflow invocations."""
import os
from typing import Any

import requests

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION = "2024-11-06"


class RunwayService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY", "")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": RUNWAY_VERSION,
        }

    def submit_workflow(
        self,
        workflow_id: str,
        prompt_node_id: str,
        image_node_id: str,
        prompt: str,
        image_uri: str,
    ) -> str:
        """POST /workflows/{workflow_id} → returns invocation_id."""
        body = {
            "nodeOutputs": {
                prompt_node_id: {
                    "prompt": {"type": "primitive", "value": prompt}
                },
                image_node_id: {
                    "image": {"type": "image", "uri": image_uri}
                },
            }
        }
        resp = requests.post(
            f"{RUNWAY_API_BASE}/workflows/{workflow_id}",
            json=body,
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def poll_workflow_invocation(self, invocation_id: str) -> dict[str, Any]:
        """GET /workflow_invocations/{invocation_id}
        Returns {"status": "PENDING|RUNNING|SUCCEEDED|FAILED", "output_url": str|None}

        The exact output field varies by Runway API version. We try `outputs`
        (list of dicts with "url") then `output` (list of strings) as a fallback.
        Log the raw response if neither matches on SUCCEEDED to aid debugging.
        """
        resp = requests.get(
            f"{RUNWAY_API_BASE}/workflow_invocations/{invocation_id}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "PENDING")

        output_url = None
        if status == "SUCCEEDED":
            outputs = data.get("outputs")
            if isinstance(outputs, list) and outputs:
                first = outputs[0]
                output_url = first.get("url") if isinstance(first, dict) else first
            if output_url is None:
                fallback = data.get("output")
                if isinstance(fallback, list) and fallback:
                    output_url = fallback[0]
                elif isinstance(fallback, str):
                    output_url = fallback
            if output_url is None:
                import logging
                logging.getLogger(__name__).warning(
                    "SUCCEEDED invocation %s has no recognised output field. Raw: %s",
                    invocation_id, data,
                )

        return {"status": status, "output_url": output_url}
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python3 -m pytest tests/test_runway_service.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/runway_service.py tests/test_runway_service.py
git commit -m "feat: rewrite RunwayService for workflow API, add tests"
```

---

## Task 3: Rewrite the Celery task

**Files:**
- Modify: `console/backend/tasks/runway_task.py` (full rewrite)

- [ ] **Step 1: Replace the file**

Replace the entire file `console/backend/tasks/runway_task.py` with:

```python
"""Celery task: poll Runway workflow invocation every 30s, timeout 10min."""
import os
import time
from pathlib import Path

import requests
import requests as _requests

from console.backend.celery_app import celery_app

RUNWAY_OUTPUT_DIR = Path(os.environ.get("ASSETS_PATH", "/app/assets/video_db")) / "runway"
POLL_INTERVAL_S = 30
TIMEOUT_S = 600  # 10 minutes


@celery_app.task(bind=True, name="tasks.animate_workflow")
def animate_workflow_task(
    self,
    asset_id: int,
    invocation_id: str,
    output_filename: str,
):
    """Poll Runway workflow invocation until SUCCEEDED/FAILED/timeout, then save video."""
    api_key = os.environ.get("RUNWAY_API_KEY", "").strip()

    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    from console.backend.services.runway_service import RunwayService

    svc = RunwayService(api_key=api_key)
    deadline = time.time() + TIMEOUT_S

    while time.time() < deadline:
        try:
            result = svc.poll_workflow_invocation(invocation_id)
        except _requests.RequestException as exc:
            raise self.retry(exc=exc, countdown=30)

        status = result["status"]

        if status == "SUCCEEDED" and result["output_url"]:
            RUNWAY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            dest = RUNWAY_OUTPUT_DIR / output_filename
            video_resp = requests.get(result["output_url"], timeout=120)
            video_resp.raise_for_status()
            dest.write_bytes(video_resp.content)

            db = SessionLocal()
            try:
                row = db.get(VideoAsset, asset_id)
                if row:
                    row.file_path = str(dest)
                    row.runway_status = "ready"
                    row.asset_type = "video_clip"
                    db.commit()
            finally:
                db.close()
            return {"status": "ready", "file_path": str(dest)}

        if status == "FAILED":
            db = SessionLocal()
            try:
                row = db.get(VideoAsset, asset_id)
                if row:
                    row.runway_status = "failed"
                    db.commit()
            finally:
                db.close()
            return {"status": "failed"}

        time.sleep(POLL_INTERVAL_S)

    # Timeout — mark as failed
    db = SessionLocal()
    try:
        row = db.get(VideoAsset, asset_id)
        if row:
            row.runway_status = "failed"
            db.commit()
    finally:
        db.close()
    return {"status": "failed", "reason": "timeout"}
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
python3 -c "from console.backend.tasks.runway_task import animate_workflow_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/runway_task.py
git commit -m "feat: replace animate_asset_task with animate_workflow_task"
```

---

## Task 4: Update the animate endpoint

**Files:**
- Modify: `console/backend/routers/production.py` — replace the `AnimateBody` class and `animate_asset_endpoint` function

- [ ] **Step 1: Add `pyyaml` import at the top of production.py if not present**

Check the top of `console/backend/routers/production.py`. If `import yaml` is not already there, the endpoint will import it inline (which is fine — keep it inline to match the existing inline-import pattern in that file).

- [ ] **Step 2: Replace AnimateBody and the animate endpoint**

Find this block in `console/backend/routers/production.py` (starting around line 236):

```python
# ── Animate still image with Runway ───────────────────────────────────────────

class AnimateBody(BaseModel):
    prompt: str
    motion_intensity: int = 2
    duration: int = 5


@router.post("/assets/{asset_id}/animate")
def animate_asset_endpoint(
    asset_id: int,
    body: AnimateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    import os
    from console.backend.models.video_asset import VideoAsset
    from console.backend.tasks.runway_task import animate_asset_task
    from console.backend.services.runway_service import RunwayService

    asset = db.get(VideoAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type != "still_image":
        raise HTTPException(status_code=400, detail="Only still images can be animated")

    api_key = os.environ.get("RUNWAY_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="RUNWAY_API_KEY not configured")

    model = os.environ.get("RUNWAY_MODEL", "gen3-alpha")
    svc = RunwayService(api_key=api_key, model=model)

    public_url = os.environ.get("PUBLIC_API_URL", "http://localhost:8080")
    image_url = f"{public_url}/api/production/assets/{asset_id}/stream"
    runway_task_id = svc.submit_image_to_video(image_url, body.prompt, body.duration, body.motion_intensity)

    child = VideoAsset(
        file_path="",
        source="runway",
        asset_type="video_clip",
        parent_asset_id=asset_id,
        generation_prompt=body.prompt,
        runway_status="pending",
        description=f"Runway animation of asset {asset_id}",
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    output_filename = f"runway_{child.id}.mp4"
    task = animate_asset_task.delay(child.id, runway_task_id, output_filename)

    return {"asset_id": child.id, "task_id": task.id, "runway_task_id": runway_task_id}
```

Replace it with:

```python
# ── Animate still image with Runway workflow ──────────────────────────────────

class AnimateBody(BaseModel):
    prompt: str
    video_type: str = "loop"


@router.post("/assets/{asset_id}/animate")
def animate_asset_endpoint(
    asset_id: int,
    body: AnimateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    import os
    import yaml
    from pathlib import Path
    from console.backend.models.video_asset import VideoAsset
    from console.backend.tasks.runway_task import animate_workflow_task
    from console.backend.services.runway_service import RunwayService

    asset = db.get(VideoAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type != "still_image":
        raise HTTPException(status_code=400, detail="Only still images can be animated")

    api_key = os.environ.get("RUNWAY_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="RUNWAY_API_KEY not configured")

    config_path = Path(__file__).parents[3] / "config" / "runway_workflows.yaml"
    with open(config_path) as f:
        workflow_config = yaml.safe_load(f)

    video_types = workflow_config.get("video_types", {})
    if body.video_type not in video_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown video_type '{body.video_type}'. Valid: {list(video_types.keys())}",
        )

    wf = video_types[body.video_type]
    svc = RunwayService(api_key=api_key)
    public_url = os.environ.get("PUBLIC_API_URL", "http://localhost:8080")
    image_uri = f"{public_url}/api/production/assets/{asset_id}/stream"

    invocation_id = svc.submit_workflow(
        workflow_id=wf["workflow_id"],
        prompt_node_id=wf["prompt_node_id"],
        image_node_id=wf["image_node_id"],
        prompt=body.prompt,
        image_uri=image_uri,
    )

    child = VideoAsset(
        file_path="",
        source="runway",
        asset_type="video_clip",
        parent_asset_id=asset_id,
        generation_prompt=body.prompt,
        runway_status="pending",
        description=f"Runway {body.video_type} animation of asset {asset_id}",
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    output_filename = f"runway_{child.id}.mp4"
    task = animate_workflow_task.delay(child.id, invocation_id, output_filename)

    return {"asset_id": child.id, "task_id": task.id, "invocation_id": invocation_id}
```

- [ ] **Step 3: Verify the router imports cleanly**

```bash
python3 -c "from console.backend.routers.production import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/production.py
git commit -m "feat: update animate endpoint to use runway workflow by video_type"
```

---

## Task 5: Update the frontend

**Files:**
- Modify: `console/frontend/src/pages/VideoAssetsPage.jsx` — `AnimateModal` component
- Modify: `console/frontend/src/api/client.js` — `animateWithRunway` body

- [ ] **Step 1: Verify `animateWithRunway` in client.js needs no change**

Open `console/frontend/src/api/client.js` and confirm the function looks like this (around line 157):

```js
  animateWithRunway: (id, body) =>
    fetchApi(`/api/production/assets/${id}/animate`, { method: 'POST', body: JSON.stringify(body) }),
```

The `body` is passed through generically — no change required. The only code that changes is the `AnimateModal` caller in the next step.

- [ ] **Step 2: Replace `AnimateModal` in VideoAssetsPage.jsx**

Find this component in `console/frontend/src/pages/VideoAssetsPage.jsx` (starts around line 173):

```jsx
function AnimateModal({ asset, onClose, onAnimated }) {
  const [prompt, setPrompt] = useState('')
  const [intensity, setIntensity] = useState(2)
  const [duration, setDuration] = useState(5)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleGenerate = async () => {
    if (!prompt) { showToast('Runway prompt is required', 'error'); return }
    setLoading(true)
    try {
      await assetsApi.animateWithRunway(asset.id, { prompt, motion_intensity: intensity, duration })
      showToast('Animation queued — check back in a few minutes', 'success')
      onAnimated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Animate with Runway →" width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleGenerate}>Animate →</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex flex-col gap-4">
        {asset.thumbnail_url && (
          <img src={assetsApi.thumbnailUrl(asset.id)} alt={asset.description} className="w-full h-32 object-cover rounded-lg" />
        )}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Runway Prompt</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] resize-none focus:outline-none focus:border-[#7c6af7]"
            placeholder="Slow rain droplets running down glass. No camera movement. Hypnotic loop."
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Motion Intensity ({intensity}/10)</label>
            <input type="range" min={1} max={10} value={intensity} onChange={e => setIntensity(Number(e.target.value))}
              className="w-full accent-[#7c6af7]" />
          </div>
          <Select label="Duration" value={duration} onChange={e => setDuration(Number(e.target.value))}>
            <option value={5}>5s</option>
            <option value={10}>10s</option>
          </Select>
        </div>
      </div>
    </Modal>
  )
}
```

Replace it with:

```jsx
const VIDEO_TYPES = ['loop']

function AnimateModal({ asset, onClose, onAnimated }) {
  const [prompt, setPrompt] = useState('')
  const [videoType, setVideoType] = useState('loop')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleGenerate = async () => {
    if (!prompt) { showToast('Runway prompt is required', 'error'); return }
    setLoading(true)
    try {
      await assetsApi.animateWithRunway(asset.id, { prompt, video_type: videoType })
      showToast('Animation queued — check back in a few minutes', 'success')
      onAnimated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Animate with Runway →" width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleGenerate}>Animate →</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex flex-col gap-4">
        {asset.thumbnail_url && (
          <img src={assetsApi.thumbnailUrl(asset.id)} alt={asset.description} className="w-full h-32 object-cover rounded-lg" />
        )}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Runway Prompt</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] resize-none focus:outline-none focus:border-[#7c6af7]"
            placeholder="Slow rain droplets running down glass. No camera movement. Hypnotic loop."
          />
        </div>
        <Select
          label="Video Type"
          value={videoType}
          onChange={e => setVideoType(e.target.value)}
        >
          {VIDEO_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </Select>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 3: Verify no lint/type errors**

```bash
cd console/frontend
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no errors. If Vite reports an error, fix it before committing.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/VideoAssetsPage.jsx
git commit -m "feat: simplify AnimateModal to prompt + video_type, drop old motion params"
```

---

## Task 6: Smoke test end-to-end

- [ ] **Step 1: Run the full backend test suite**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all tests pass. Fix any failures before proceeding.

- [ ] **Step 2: Start the backend**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
./console/start.sh
```

In a second terminal:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run dev
```

- [ ] **Step 3: Manual smoke test**

1. Open `http://localhost:5173` → log in → go to **Video Assets**
2. Upload or pick an existing still image asset
3. Click the **Animate** button on a still image row
4. Verify the modal shows: **Runway Prompt** textarea + **Video Type** dropdown (with "loop")
5. Verify the old Motion Intensity slider and Duration dropdown are gone
6. Enter a prompt, click **Animate →**
7. Verify the network request body in browser DevTools → Network is `{"prompt": "...", "video_type": "loop"}`
8. Verify the API returns `{"asset_id": ..., "task_id": ..., "invocation_id": ...}` (not `runway_task_id`)
9. Verify a new asset row appears with `runway_status = pending`

- [ ] **Step 4: Verify unknown video_type returns 400**

```bash
curl -s -X POST http://localhost:8080/api/production/assets/1/animate \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "video_type": "invalid_type"}' | python3 -m json.tool
```

Expected:
```json
{"detail": "Unknown video_type 'invalid_type'. Valid: ['loop']"}
```

- [ ] **Step 5: Final commit if any cleanup needed**

```bash
git add -p
git commit -m "fix: smoke test cleanup"
```
