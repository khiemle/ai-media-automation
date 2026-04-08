"""WebSocket endpoint — broadcasts pipeline job status every 2s."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS connected — {len(self.active)} client(s)")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"WS disconnected — {len(self.active)} client(s)")

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def _get_stats() -> dict:
    """Fetch pipeline stats from DB without holding an open session."""
    try:
        from console.backend.database import SessionLocal
        from console.backend.models.pipeline_job import PipelineJob
        from sqlalchemy import func

        db = SessionLocal()
        try:
            rows = (
                db.query(PipelineJob.status, func.count(PipelineJob.id))
                .group_by(PipelineJob.status)
                .all()
            )
            counts = {r[0]: r[1] for r in rows}
            recent = (
                db.query(PipelineJob)
                .order_by(PipelineJob.created_at.desc())
                .limit(10)
                .all()
            )
            jobs = [
                {
                    "id":         j.id,
                    "job_type":   j.job_type,
                    "status":     j.status,
                    "progress":   j.progress,
                    "script_id":  j.script_id,
                    "error":      j.error,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                }
                for j in recent
            ]
            return {
                "stats": {
                    "queued":    counts.get("queued", 0),
                    "running":   counts.get("running", 0),
                    "completed": counts.get("completed", 0),
                    "failed":    counts.get("failed", 0),
                    "total":     sum(counts.values()),
                },
                "recent_jobs": jobs,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"WS stats fetch failed: {e}")
        return {"stats": {}, "recent_jobs": []}


@router.websocket("/ws/pipeline")
async def pipeline_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = _get_stats()
            await manager.broadcast({
                "type":      "pipeline_update",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **data,
            })
            # Also listen for client messages (ping/pong keepalive)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)
