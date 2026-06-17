# routes/app/notifications.py
from fastapi import APIRouter, Depends, Query
from prisma.enums import AuditEventType
from middlewares.auth import get_current_user, require_platform
from utils.ApiResponse import api_response
from services.app import notification_service

notifications_router = APIRouter(
    prefix="/notifications",
    tags=["App — Notifications"],
    dependencies=[Depends(require_platform("app"))],
)


@notifications_router.get("", summary="Get paginated notification list")
async def get_notifications(
    current_user=Depends(get_current_user),
    cursor: str | None = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    event_types: list[AuditEventType] | None = Query(default=None, alias="eventTypes"),
):
    result = await notification_service.get_notifications(
        current_user=current_user,
        cursor=cursor,
        page_size=page_size,
        event_types=event_types,
    )
    return api_response(200, result, "Notifications fetched successfully")


@notifications_router.get("/unread-count", summary="Get unread notification count")
async def get_unread_count(
    current_user=Depends(get_current_user),
    event_types: list[AuditEventType] | None = Query(default=None, alias="eventTypes"),
):
    result = await notification_service.get_unread_count(
        current_user=current_user,
        event_types=event_types,
    )
    return api_response(200, result, "Unread count fetched successfully")


@notifications_router.patch("/read-all", summary="Mark all notifications as read")
async def mark_all_read(
    current_user=Depends(get_current_user),
    event_types: list[AuditEventType] | None = Query(default=None, alias="eventTypes"),
):
    result = await notification_service.mark_all_notifications_read(
        current_user=current_user,
        event_types=event_types,
    )
    return api_response(200, result, "Notifications marked as read")


@notifications_router.patch("/{notification_id}/read", summary="Mark a single notification as read")
async def mark_notification_read(
    notification_id: str,
    current_user=Depends(get_current_user),
):
    result = await notification_service.mark_notification_read(
        current_user=current_user,
        notification_id=notification_id,
    )
    return api_response(200, result, "Notification marked as read")
