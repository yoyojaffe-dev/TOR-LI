"""Client authentication — phone (SMS) OTP login via Supabase Auth.

Two steps, both thin wrappers over GoTrue:

* ``POST /auth/send-otp``   -> ``auth.sign_in_with_otp({phone})`` — GoTrue sends
  the SMS through the Twilio provider configured in the Supabase dashboard.
* ``POST /auth/verify-otp`` -> ``auth.verify_otp({phone, token, type})`` — on a
  correct code GoTrue returns a session (access + refresh JWTs) we hand back.

Barbers do NOT use this router: the dashboard logs in with email/password directly
against Supabase Auth (``signInWithPassword``). GoTrue owns code generation,
hashing, expiry, attempt-lockout, and rate-limiting; we never store OTP codes and
the Twilio credentials never enter this process.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ActionResult, SendOtpRequest, SessionResponse, VerifyOtpRequest
from app.supabase_client import get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])


def _gotrue_status(exc: Exception) -> int:
    """Map a GoTrue error onto an HTTP status for the client.

    GoTrue's ``AuthApiError`` carries the upstream HTTP ``status``; 429 is a
    genuine rate-limit, 4xx means a bad request / wrong code, and anything else
    (provider not configured, GoTrue down) surfaces as 503.
    """
    upstream = getattr(exc, "status", None)
    if upstream == status.HTTP_429_TOO_MANY_REQUESTS:
        return status.HTTP_429_TOO_MANY_REQUESTS
    if isinstance(upstream, int) and 400 <= upstream < 500:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_503_SERVICE_UNAVAILABLE


@router.post("/send-otp", response_model=ActionResult)
def send_otp(req: SendOtpRequest) -> ActionResult:
    """Send an SMS one-time code to ``phone`` (creates the account on first use)."""
    try:
        get_supabase().auth.sign_in_with_otp({"phone": req.phone})
    except Exception as exc:
        raise HTTPException(status_code=_gotrue_status(exc), detail="could not send code") from exc
    return ActionResult(success=True, message="code sent")


@router.post("/verify-otp", response_model=SessionResponse)
def verify_otp(req: VerifyOtpRequest) -> SessionResponse:
    """Verify the SMS code and return a GoTrue session (access + refresh tokens)."""
    try:
        result: Any = get_supabase().auth.verify_otp(
            {"phone": req.phone, "token": req.token, "type": "sms"}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=_gotrue_status(exc), detail="invalid or expired code"
        ) from exc

    session = getattr(result, "session", None)
    user = getattr(result, "user", None)
    if session is None or user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired code"
        )

    return SessionResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_at=getattr(session, "expires_at", None),
        expires_in=getattr(session, "expires_in", None),
        user_id=str(user.id),
    )
