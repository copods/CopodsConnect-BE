"""Sign-in is allowed only for verified Google Workspace users @copods.co."""

from __future__ import annotations

import re

COPODS_SIGNIN_DOMAIN = "copods.co"
COPODS_EMAIL_SUFFIX = f"@{COPODS_SIGNIN_DOMAIN}"

# Local part: letters, digits, . _ - + (no spaces, no extra @)
_COPODS_EMAIL_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9._+-]*[a-z0-9])?@copods\.co$",
    re.IGNORECASE,
)


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def is_allowed_signin_email(email: str | None) -> bool:
    """
    Strict @copods.co only:
    - exact host copods.co (not gmail.com, not evilcopods.co, not subdomains)
    - sane local part via regex
    """
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 254:
        return False
    if normalized.count("@") != 1:
        return False
    if not normalized.endswith(COPODS_EMAIL_SUFFIX):
        return False
    local, host = normalized.rsplit("@", 1)
    if host != COPODS_SIGNIN_DOMAIN or not local:
        return False
    return _COPODS_EMAIL_RE.match(normalized) is not None


def _is_truthy_verified(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return False


def assert_copods_google_workspace(
    *,
    userinfo: dict,
    id_token_claims: dict | None,
) -> str:
    """
    Enforce Copods-only login using Google userinfo + id_token (tokeninfo).
    Raises ValueError with a safe message if the account is not allowed.
    """
    email = normalize_email(userinfo.get("email"))
    if not email or not is_allowed_signin_email(email):
        raise ValueError("not_copods_email")

    if not _is_truthy_verified(userinfo.get("email_verified")):
        raise ValueError("email_not_verified")

    hd = (userinfo.get("hd") or "").strip().lower()
    if hd != COPODS_SIGNIN_DOMAIN:
        # Personal Gmail / other Workspace tenants have no hd or a different hd
        raise ValueError("not_copods_workspace")

    if not id_token_claims:
        raise ValueError("missing_id_token")

    token_email = normalize_email(id_token_claims.get("email"))
    if token_email != email:
        raise ValueError("email_mismatch")

    if not _is_truthy_verified(id_token_claims.get("email_verified")):
        raise ValueError("token_email_not_verified")

    token_hd = (id_token_claims.get("hd") or "").strip().lower()
    if token_hd != COPODS_SIGNIN_DOMAIN:
        raise ValueError("token_not_copods_workspace")

    if not is_allowed_signin_email(token_email):
        raise ValueError("token_not_copods_email")

    return email
