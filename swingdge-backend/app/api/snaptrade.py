"""
SnapTrade setup endpoints — registration and Wealthsimple connection.

These are one-time setup endpoints used from the Settings page.
After registration, save the returned userId + userSecret to Render env vars.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.utils.auth import verify_token
from app.services import snaptrade as snaptrade_svc
from app.config import get_settings

router = APIRouter(prefix="/api/snaptrade", tags=["snaptrade"])
settings = get_settings()


@router.post("/register")
async def register_user(_: str = Depends(verify_token)):
    """
    Register this app as a SnapTrade user. Run once during initial setup.
    Returns userId and userSecret — add both to Render environment variables.
    """
    try:
        result = await snaptrade_svc.register_user()
        return {
            "userId": result.get("userId"),
            "userSecret": result.get("userSecret"),
            "message": "Save these values as SNAPTRADE_USER_ID and SNAPTRADE_USER_SECRET_ENCRYPTED in Render environment variables, then redeploy.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connect")
async def get_connect_link(_: str = Depends(verify_token)):
    """
    Returns the Wealthsimple OAuth URL. Open this URL in a browser to link accounts.
    """
    if not settings.snaptrade_user_id:
        raise HTTPException(
            status_code=400,
            detail="SNAPTRADE_USER_ID not set. Call POST /api/snaptrade/register first.",
        )
    try:
        redirect_uri = "https://swing-edge.onrender.com/api/snaptrade/callback"
        link = await snaptrade_svc.get_connection_link(redirect_uri)
        return {"url": link}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def connection_callback():
    """
    SnapTrade redirects here after Wealthsimple OAuth. Just confirms success.
    """
    return {"message": "Wealthsimple connected successfully. You can close this tab."}


@router.get("/status")
async def snaptrade_status(_: str = Depends(verify_token)):
    """
    Shows whether SnapTrade user is registered and has linked accounts.
    """
    user_id = settings.snaptrade_user_id
    is_registered = bool(user_id)

    accounts = []
    if is_registered:
        try:
            accounts = await snaptrade_svc.get_accounts()
        except Exception:
            pass

    return {
        "registered": is_registered,
        "user_id": user_id if is_registered else None,
        "accounts_linked": len(accounts),
        "accounts": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "institution": a.get("institution_name"),
            }
            for a in accounts
        ],
    }
