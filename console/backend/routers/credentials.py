"""Credentials router — platform OAuth config, token management, OAuth callback."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.credential_service import CredentialService

router = APIRouter(prefix="/credentials", tags=["credentials"])


class UpsertCredentialBody(BaseModel):
    name: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str | None = None
    scopes: list[str] | None = None
    auth_endpoint: str | None = None
    token_endpoint: str | None = None


@router.get("")
def list_credentials(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return CredentialService(db).list_credentials()


@router.get("/{cred_id}")
def get_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return CredentialService(db).get_credential(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{platform}")
def upsert_credential(
    platform: str,
    body: UpsertCredentialBody,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    if platform not in ("youtube", "tiktok", "instagram"):
        raise HTTPException(status_code=400, detail="Platform must be youtube, tiktok, or instagram")
    return CredentialService(db).upsert_credential(platform, body.model_dump(exclude_none=True))


@router.get("/{platform}/oauth-url")
def get_oauth_url(
    platform: str,
    state: str | None = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    try:
        url = CredentialService(db).build_oauth_url(platform, state)
        return {"url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{platform}/callback")
def oauth_callback(
    platform: str,
    code: str = Query(...),
    state: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """OAuth callback — exchanges auth code for tokens and stores encrypted."""
    try:
        cred = CredentialService(db).exchange_code(platform, code)
        return {"ok": True, "platform": platform, "status": cred["status"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {e}")


@router.post("/{cred_id}/refresh")
def refresh_token(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    try:
        return CredentialService(db).refresh_token(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cred_id}/test")
def test_connection(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return CredentialService(db).test_connection(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{cred_id}/disconnect")
def disconnect(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    try:
        return CredentialService(db).disconnect(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
