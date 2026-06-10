# routes/app/notifications.py
#
# FRONTEND CONTRACT:
#   All endpoints require a valid app JWT (platform: "app").
#
#   Recommended polling flow:
#     1. On app open / foreground resume → GET /notifications/unread-count
#        Pass ?types= scoped to the current page surface to get the badge count.
#     2. User taps bell → GET /notifications (pass ?types= for the surface)
#     3. After fetching → PATCH /notifications/read-all (same ?types= filter)
#        This marks only that surface's notifications as read so the other
#        surface's badge is unaffected.
#     4. User taps a single notification → PATCH /notifications/{id}/read
#
#   Type filter values per surface:
#     Feed page:
#       POST_LIKE, POST_COMMENT, POST_TAG, COMMENT_REPLY, COMMENT_TAG,
#       BIRTHDAY_CELEBRATION, ANNIVERSARY_CELEBRATION,
#       PEER_BIRTHDAY, PEER_ANNIVERSARY, POST_REMOVED_BY_MODERATION
#     Appreciation page:
#       APPRECIATION_RECEIVED

from fastapi import APIRouter, Depends, Query
from prisma.enums import NotificationType
from middlewares.auth import get_current_user, require_platform
from utils.ApiResponse import api_response
from services.app import notification_service

notifications_router = APIRouter(
    prefix="/notifications",
    tags=["App — Notifications"],
    dependencies=[Depends(require_platform("app"))],
)


@notifications_router.get(
    "",
    summary="Get paginated notification list",
    description=(
        "Returns cursor-paginated notifications for the current user, newest first. "
        "Pass ?types= (comma-separated NotificationType values) to filter by surface. "
        "After fetching, call PATCH /notifications/read-all with the same ?types= filter."
    ),
)
async def get_notifications(
    current_user=Depends(get_current_user),
    cursor: str | None = Query(default=None, description="Cursor from previous page (last notification id)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Number of notifications per page"),
    types: list[NotificationType] | None = Query(default=None, description="Filter by notification type(s)"),
):
    result = await notification_service.get_notifications(
        current_user=current_user,
        cursor=cursor,
        page_size=page_size,
        types=types,
    )
    return api_response(200, result, "Notifications fetched successfully")


@notifications_router.get(
    "/unread-count",
    summary="Get unread notification count",
    description=(
        "Returns the count of unread notifications for the current user. "
        "Pass ?types= to get a per-surface badge count. "
        "FRONTEND: poll this every 30-60 seconds while the app is foregrounded, "
        "and call it immediately on app open / foreground resume."
    ),
)
async def get_unread_count(
    current_user=Depends(get_current_user),
    types: list[NotificationType] | None = Query(default=None, description="Filter by notification type(s)"),
):
    result = await notification_service.get_unread_count(
        current_user=current_user,
        types=types,
    )
    return api_response(200, result, "Unread count fetched successfully")


@notifications_router.patch(
    "/read-all",
    summary="Mark all notifications as read",
    description=(
        "Marks all unread notifications as read for the current user. "
        "Pass ?types= to scope to a specific surface only — "
        "e.g. pass the feed types to mark only feed notifications as read "
        "without affecting the appreciation page badge."
    ),
)
async def mark_all_read(
    current_user=Depends(get_current_user),
    types: list[NotificationType] | None = Query(default=None, description="Scope to specific notification type(s)"),
):
    result = await notification_service.mark_all_notifications_read(
        current_user=current_user,
        types=types,
    )
    return api_response(200, result, "Notifications marked as read")


@notifications_router.patch(
    "/{notification_id}/read",
    summary="Mark a single notification as read",
    description="Marks a specific notification as read. Idempotent — safe to call multiple times.",
)
async def mark_notification_read(
    notification_id: str,
    current_user=Depends(get_current_user),
):
    result = await notification_service.mark_notification_read(
        current_user=current_user,
        notification_id=notification_id,
    )
    return api_response(200, result, "Notification marked as read")