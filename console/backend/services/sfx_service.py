import os
from pathlib import Path

from sqlalchemy.orm import Session

SFX_DIR = Path(os.environ.get("SFX_PATH", "./assets/sfx"))


def _sfx_to_dict(s) -> dict:
    return {
        "id":          s.id,
        "title":       s.title,
        "file_path":   s.file_path,
        "source":      s.source,
        "sound_type":  s.sound_type,
        "duration_s":  s.duration_s,
        "usage_count": s.usage_count,
        "created_at":  s.created_at.isoformat() if s.created_at else None,
    }


class SfxService:
    def __init__(self, db: Session):
        self.db = db

    def _model(self):
        from console.backend.models.sfx_asset import SfxAsset
        return SfxAsset

    def list_sfx(self, sound_type: str | None = None, search: str | None = None) -> list[dict]:
        SfxAsset = self._model()
        q = self.db.query(SfxAsset)
        if sound_type:
            q = q.filter(SfxAsset.sound_type == sound_type)
        if search:
            q = q.filter(SfxAsset.title.ilike(f"%{search}%"))
        return [_sfx_to_dict(s) for s in q.order_by(SfxAsset.created_at.desc()).all()]

    def list_sound_types(self) -> list[str]:
        SfxAsset = self._model()
        rows = (
            self.db.query(SfxAsset.sound_type)
            .distinct()
            .filter(SfxAsset.sound_type.isnot(None))
            .all()
        )
        return sorted([r[0] for r in rows])

    def import_sfx(
        self,
        title: str,
        sound_type: str,
        source: str,
        file_bytes: bytes,
        filename: str,
        sfx_dir: Path | None = None,
    ) -> dict:
        SfxAsset = self._model()
        sfx_dir = sfx_dir or SFX_DIR
        sfx_dir.mkdir(parents=True, exist_ok=True)

        row = SfxAsset(title=title, sound_type=sound_type, source=source, file_path="")
        self.db.add(row)
        self.db.flush()

        ext = Path(filename).suffix or ".wav"
        dest = sfx_dir / f"sfx_{row.id}{ext}"
        dest.write_bytes(file_bytes)
        row.file_path = str(dest)
        self.db.commit()
        self.db.refresh(row)
        return _sfx_to_dict(row)

    def delete_sfx(self, sfx_id: int) -> None:
        SfxAsset = self._model()
        row = self.db.get(SfxAsset, sfx_id)
        if not row:
            raise KeyError(f"SFX {sfx_id} not found")
        path = Path(row.file_path)
        self.db.delete(row)
        self.db.commit()
        if path.exists():
            path.unlink(missing_ok=True)
