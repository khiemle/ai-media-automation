"""Credentials router — platform OAuth config, token management, OAuth callback."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
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
    """OAuth callback — exchanges auth code for tokens and stores encrypted.

    If state starts with 'cred_' (wizard flow), routes to the specific credential.
    Otherwise falls back to the legacy platform-wide credential lookup.
    """
    try:
        svc = CredentialService(db)
        if state and state.startswith("cred_"):
            cred_id = int(state.removeprefix("cred_"))
            svc.exchange_code_for_credential(cred_id, code)
        else:
            svc.exchange_code(platform, code)
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;padding:2rem;background:#0d0d0f;color:#34d399'>"
            "<h2>✓ Authorization successful</h2>"
            "<p style='color:#9090a8'>You can close this tab and return to the console.</p>"
            "<script>setTimeout(()=>window.close(),2000)</script>"
            "</body></html>"
        )
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


# ── YouTube Setup Wizard ──────────────────────────────────────────────────────

class WizardStartBody(BaseModel):
    name: str
    client_id: str
    client_secret: str
    redirect_uri: str


@router.post("/youtube/setup/start", status_code=201)
def wizard_start(
    body: WizardStartBody,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    """Create a new pending YouTube credential and return the OAuth URL."""
    svc = CredentialService(db)
    cred = svc.create_youtube_credential(
        name=body.name,
        client_id=body.client_id,
        client_secret=body.client_secret,
        redirect_uri=body.redirect_uri,
    )
    cred_id = cred["id"]
    oauth_url = svc.build_oauth_url_for_credential(cred_id, state=f"cred_{cred_id}")
    return {"cred_id": cred_id, "oauth_url": oauth_url}


@router.get("/youtube/setup/status/{cred_id}")
def wizard_status(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Poll this endpoint to detect when OAuth callback has completed."""
    try:
        cred = CredentialService(db).get_credential(cred_id)
        return {"status": cred["status"], "connected_at": cred.get("last_refreshed")}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/youtube/setup/verify/{cred_id}")
def wizard_verify(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Call YouTube channels.list to confirm the token works."""
    try:
        return CredentialService(db).verify_youtube_credential(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/youtube/setup/create-channel/{cred_id}", status_code=201)
def wizard_create_channel(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Create a Channel row linked to the credential (calls verify internally)."""
    try:
        return CredentialService(db).create_channel_from_credential(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
