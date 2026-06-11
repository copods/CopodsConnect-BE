# services/app/storage_service.py
import asyncio
import os
import re
from functools import lru_cache
from uuid import uuid4

from supabase import Client, create_client
from storage3.types import CreateSignedUploadUrlOptions
from utils.exceptions import AppException

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB (documented limit; size enforced on app + optional later)


@lru_cache
def _get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise AppException(
            500,
            "Supabase storage is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).",
        )
    return create_client(url, key)


def _get_bucket() -> str:
    return os.getenv("SUPABASE_STORAGE_BUCKET", "post-media").strip()


def _public_url(path: str) -> str:
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    bucket = _get_bucket()
    return f"{base}/storage/v1/object/public/{bucket}/{path}"


def _extension_for_content_type(content_type: str) -> str:
    normalized = content_type.strip().lower()
    if normalized not in ALLOWED_CONTENT_TYPES:
        raise AppException(
            400,
            f"Unsupported content type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )
    return ALLOWED_CONTENT_TYPES[normalized]


def _sanitize_user_id(user_id: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", user_id):
        raise AppException(400, "Invalid user id for storage path.")
    return user_id


def _create_signed_upload_sync(user_id: str, content_type: str) -> dict:
    ext = _extension_for_content_type(content_type)
    safe_user_id = _sanitize_user_id(user_id)
    path = f"{safe_user_id}/{uuid4()}.{ext}"
    bucket = _get_bucket()

    supabase = _get_supabase()
    result = supabase.storage.from_(bucket).create_signed_upload_url(
        path,
        options=CreateSignedUploadUrlOptions(upsert="true"),
    )

    # supabase-py may return dict or object
    if isinstance(result, dict):
        signed = result.get("signedUrl") or result.get("signed_url")
        token = result.get("token")
        storage_path = result.get("path") or path
    else:
        signed = getattr(result, "signedUrl", None) or getattr(result, "signed_url", None)
        token = getattr(result, "token", None)
        storage_path = getattr(result, "path", path)

    if not signed:
        raise AppException(500, "Failed to create signed upload URL from Supabase.")

    return {
        "uploadUrl": signed,
        "publicUrl": _public_url(storage_path),
        "path": storage_path,
        "contentType": content_type,
        "token": token,  # optional; app uses PUT to uploadUrl
    }


async def create_post_media_upload_url(user_id: str, content_type: str) -> dict:
    payload = await asyncio.to_thread(_create_signed_upload_sync, user_id, content_type)
    # Do not expose token to client unless you need upload_to_signed_url flow
    payload.pop("token", None)
    return payload


def _create_avatar_upload_sync(user_id: str, content_type: str) -> dict:
    ext = _extension_for_content_type(content_type)
    safe_user_id = _sanitize_user_id(user_id)
    path = f"avatars/{safe_user_id}/{uuid4()}.{ext}"
    bucket = _get_bucket()

    supabase = _get_supabase()
    result = supabase.storage.from_(bucket).create_signed_upload_url(
        path,
        options=CreateSignedUploadUrlOptions(upsert="true"),
    )

    if isinstance(result, dict):
        signed = result.get("signedUrl") or result.get("signed_url")
        storage_path = result.get("path") or path
    else:
        signed = getattr(result, "signedUrl", None) or getattr(result, "signed_url", None)
        storage_path = getattr(result, "path", path)

    if not signed:
        raise AppException(500, "Failed to create signed upload URL from Supabase.")

    return {
        "uploadUrl": signed,
        "publicUrl": _public_url(storage_path),
        "path": storage_path,
        "contentType": content_type,
    }


async def create_avatar_upload_url(user_id: str, content_type: str) -> dict:
    """Generate a signed Supabase upload URL for a profile picture.
    Files are stored under avatars/{user_id}/ to separate them from post media.
    """
    return await asyncio.to_thread(_create_avatar_upload_sync, user_id, content_type)


def assert_allowed_post_media_url(url: str) -> None:
    """Optional: call from create_post to reject non-Supabase URLs."""
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    bucket = _get_bucket()
    prefix = f"{base}/storage/v1/object/public/{bucket}/"
    if not url.startswith(prefix):
        raise AppException(400, "Media URL must be hosted on Copods storage.")