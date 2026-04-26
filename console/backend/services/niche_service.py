"""NicheService — CRUD for the niches table."""
from sqlalchemy.orm import Session
from console.backend.models.niche import Niche
from console.backend.models.audit_log import AuditLog


def _audit(db, user_id, action, name):
    db.add(AuditLog(user_id=user_id, action=action, target_type="niche", target_id=name))


class NicheService:
    def __init__(self, db: Session):
        self.db = db

    def list_niches(self) -> list[dict]:
        """Return all niches with script_count."""
        try:
            from database.models import GeneratedScript
            rows = self.db.query(Niche).order_by(Niche.name).all()
            result = []
            for n in rows:
                count = self.db.query(GeneratedScript).filter(GeneratedScript.niche == n.name).count()
                result.append({"id": n.id, "name": n.name, "script_count": count, "created_at": n.created_at.isoformat() if n.created_at else None})
            return result
        except Exception:
            rows = self.db.query(Niche).order_by(Niche.name).all()
            return [{"id": n.id, "name": n.name, "script_count": 0, "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]

    def create_niche(self, name: str, user_id: int) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("Niche name cannot be empty")
        existing = self.db.query(Niche).filter(Niche.name == name).first()
        if existing:
            raise ValueError(f"Niche '{name}' already exists")
        niche = Niche(name=name)
        self.db.add(niche)
        _audit(self.db, user_id, "create_niche", name)
        self.db.commit()
        self.db.refresh(niche)
        return {"id": niche.id, "name": niche.name, "script_count": 0, "created_at": niche.created_at.isoformat() if niche.created_at else None}

    def delete_niche(self, niche_id: int, user_id: int) -> None:
        niche = self.db.query(Niche).filter(Niche.id == niche_id).first()
        if not niche:
            raise KeyError(f"Niche {niche_id} not found")
        try:
            from database.models import GeneratedScript
            count = self.db.query(GeneratedScript).filter(GeneratedScript.niche == niche.name).count()
            if count > 0:
                raise ValueError(f"Cannot delete '{niche.name}' — used by {count} script(s)")
        except ImportError:
            pass
        _audit(self.db, user_id, "delete_niche", niche.name)
        self.db.delete(niche)
        self.db.commit()

    def get_or_create(self, name: str, user_id: int) -> dict:
        name = name.strip()
        existing = self.db.query(Niche).filter(Niche.name == name).first()
        if existing:
            return {"id": existing.id, "name": existing.name}
        return self.create_niche(name, user_id)
