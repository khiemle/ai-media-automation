from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.niche_service import NicheService

router = APIRouter(prefix="/niches", tags=["niches"])


class CreateNicheBody(BaseModel):
    name: str


@router.get("")
def list_niches(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return NicheService(db).list_niches()


@router.post("", status_code=201)
def create_niche(
    body: CreateNicheBody,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return NicheService(db).create_niche(body.name, user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{niche_id}", status_code=204)
def delete_niche(
    niche_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        NicheService(db).delete_niche(niche_id, user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
