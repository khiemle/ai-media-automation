"""Per-YouTube-video render WebSocket — broadcasts state updates pushed via Redis pub/sub."""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from console.backend.auth import decode_token

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_state(video_id: int) -> dict:
    from console.backend.database import SessionLocal
    from console.backend.services.youtube_render_state import get_render_state
    db = SessionLocal()
    try:
        return get_render_state(db, video_id)
    except KeyError:
        return {"error": "not_found"}
    finally:
        db.close()


@router.websocket("/ws/render/youtube/{video_id}")
async def youtube_render_ws(websocket: WebSocket, video_id: int, token: str = Query(...)):
    try:
        decode_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    loop = asyncio.get_running_loop()

    # Subscribe FIRST so we don't miss events between subscribe and snapshot
    from console.backend.services.pipeline_service import _get_redis
    pubsub = _get_redis().pubsub()
    pubsub.subscribe(f"render:youtube:{video_id}")

    # Initial snapshot
    try:
        snap = await loop.run_in_executor(None, _get_state, video_id)
        await websocket.send_json({"type": "snapshot", **snap})
    except Exception as e:
        logger.warning(f"WS youtube render snapshot failed: {e}")

    async def _poll_pubsub():
        idle_polls = 0
        while True:
            msg = await loop.run_in_executor(None, pubsub.get_message, True, 1.0)
            if msg and msg.get("type") == "message":
                idle_polls = 0
                snap = await loop.run_in_executor(None, _get_state, video_id)
                await websocket.send_json({"type": "update", **snap})
            else:
                idle_polls += 1
                if idle_polls >= 10:
                    idle_polls = 0
                    await websocket.send_json({"type": "ping"})

    try:
        await _poll_pubsub()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS youtube render error: {e}")
    finally:
        try:
            pubsub.close()
        except Exception:
            pass
