"""SQLAlchemy-backed audit sink writing to mcp_tool_calls."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, MetaData, Table


_meta = MetaData()


def _table() -> Table:
    """Lazy reflect — avoids ORM model duplication."""
    from console.backend.database import engine
    if "mcp_tool_calls" not in _meta.tables:
        _meta.reflect(bind=engine, only=["mcp_tool_calls"])
    return _meta.tables["mcp_tool_calls"]


class DbAuditSink:
    async def write(self, **kw: Any) -> None:
        # Run the synchronous SQLAlchemy write in a thread.
        import asyncio
        await asyncio.get_running_loop().run_in_executor(None, self._write_sync, kw)

    def _write_sync(self, kw: dict) -> None:
        from console.backend.database import SessionLocal
        with SessionLocal() as s:
            s.execute(insert(_table()).values(
                called_at=datetime.now(timezone.utc),
                transport=kw["transport"],
                actor_jwt_sub=kw.get("actor_jwt_sub"),
                tool_name=kw["tool_name"],
                action=kw.get("action"),
                args_redacted=kw.get("args_redacted"),
                ok=kw["ok"],
                error_code=kw.get("error_code"),
                duration_ms=kw["duration_ms"],
                task_id=kw.get("task_id"),
            ))
            s.commit()
