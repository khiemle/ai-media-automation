"""SystemService — hardware metrics, service health, cron schedule, error logs."""
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


class SystemService:

    # ── Hardware metrics ──────────────────────────────────────────────────────

    def get_health(self) -> dict:
        return {
            "cpu":      self._cpu(),
            "ram":      self._ram(),
            "disk":     self._disk(),
            "gpu":      self._gpu(),
            "services": self._services(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _cpu(self) -> dict:
        try:
            import psutil
            pct = psutil.cpu_percent(interval=0.2)
            count = psutil.cpu_count()
            return {"percent": pct, "cores": count}
        except ImportError:
            return {"percent": 0, "cores": 0, "error": "psutil not installed"}

    def _ram(self) -> dict:
        try:
            import psutil
            m = psutil.virtual_memory()
            return {
                "percent": m.percent,
                "used_gb": round(m.used / 1e9, 1),
                "total_gb": round(m.total / 1e9, 1),
            }
        except ImportError:
            return {"percent": 0, "used_gb": 0, "total_gb": 0}

    def _disk(self) -> dict:
        try:
            import psutil
            d = psutil.disk_usage("/")
            return {
                "percent": d.percent,
                "used_gb": round(d.used / 1e9, 1),
                "total_gb": round(d.total / 1e9, 1),
            }
        except ImportError:
            return {"percent": 0, "used_gb": 0, "total_gb": 0}

    def _gpu(self) -> dict:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                parts = [p.strip() for p in result.stdout.strip().split(",")]
                return {
                    "available":   True,
                    "percent":     int(parts[0]),
                    "mem_used_mb": int(parts[1]),
                    "mem_total_mb":int(parts[2]),
                    "temp_c":      int(parts[3]),
                }
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return {"available": False}

    # ── Service health checks ─────────────────────────────────────────────────

    def _services(self) -> list[dict]:
        checks = [
            ("PostgreSQL",  self._check_postgres),
            ("Redis",       self._check_redis),
            ("Celery",      self._check_celery),
            ("FastAPI",     lambda: {"ok": True, "note": "self"}),
            ("Ollama",      self._check_ollama),
            ("ffmpeg",      self._check_ffmpeg),
        ]
        return [
            {"name": name, **fn()}
            for name, fn in checks
        ]

    def _check_postgres(self) -> dict:
        try:
            result = subprocess.run(["pg_isready"], capture_output=True, timeout=3)
            return {"ok": result.returncode == 0}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_redis(self) -> dict:
        try:
            result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True, timeout=3)
            return {"ok": result.stdout.strip() == "PONG"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_celery(self) -> dict:
        try:
            from console.backend.celery_app import celery_app
            inspect = celery_app.control.inspect(timeout=2)
            active = inspect.active()
            return {"ok": active is not None, "workers": len(active) if active else 0}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_ollama(self) -> dict:
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
            return {"ok": resp.status_code == 200}
        except Exception:
            return {"ok": False}

    def _check_ffmpeg(self) -> dict:
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
            return {"ok": result.returncode == 0}
        except Exception:
            return {"ok": False}

    # ── Cron schedule ─────────────────────────────────────────────────────────

    def get_cron(self) -> list[dict]:
        """Return Celery beat schedule as a list of cron entries."""
        try:
            from console.backend.celery_app import celery_app
            schedule = celery_app.conf.beat_schedule or {}
            result = []
            for name, entry in schedule.items():
                result.append({
                    "name":    name,
                    "task":    entry.get("task", ""),
                    "schedule": str(entry.get("schedule", "")),
                    "args":    entry.get("args", []),
                })
            return result
        except Exception as e:
            logger.warning(f"Cron schedule fetch failed: {e}")
            return []

    # ── Error logs ────────────────────────────────────────────────────────────

    def get_errors(self, limit: int = 50) -> list[dict]:
        """Tail log files and return recent ERROR/WARNING lines."""
        entries = []
        log_files = [
            ("backend",  LOG_DIR / "backend.log"),
            ("celery",   LOG_DIR / "celery.log"),
            ("frontend", LOG_DIR / "frontend.log"),
        ]
        for source, path in log_files:
            if not path.exists():
                continue
            try:
                with open(path, "r", errors="replace") as f:
                    lines = f.readlines()
                for line in lines[-500:]:
                    upper = line.upper()
                    if "ERROR" in upper or "WARNING" in upper or "CRITICAL" in upper:
                        level = "error" if "ERROR" in upper or "CRITICAL" in upper else "warning"
                        entries.append({
                            "source": source,
                            "level":  level,
                            "message": line.strip()[:200],
                        })
            except Exception:
                pass

        # Most recent first
        entries.reverse()
        return entries[:limit]
