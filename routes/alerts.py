# routes/alerts.py
from models.schemas.alerts import AlertCommentOut
import json
from fastapi import APIRouter, Depends, Query
from typing import Optional

from middlewares.auth import require_admin, require_platform
from services.alert_service import resolve_alert
from db.client import db
from prisma.enums import AlertAction
from utils.ApiResponse import api_response
from utils.exceptions import AppException
from models.schemas.alerts import (
    ResolveAlertRequest,
    ResolveAlertAction,
    AlertOut,
    AlertListResponse,
    ResolveAlertResponse,
    AlertPostOut,
    AlertPostMediaOut,
    AlertUserOut,
    AlertResolvedByOut,
)

alerts_router = APIRouter(
    prefix="/alerts",
    tags=["Admin Alerts"],
    dependencies=[Depends(require_platform("panel"))],
)


def _serialize_alert(alert) -> dict:
    post = getattr(alert, "post", None)
    comment = getattr(alert, "comment", None)
    reported_user = getattr(alert, "reportedUser", None)
    resolved_by = getattr(alert, "resolvedBy", None)

    return AlertOut(
        id=alert.id,
        postId=alert.postId,
        commentId=alert.commentId,
        reportedUserId=alert.reportedUserId,
        flagDetails=json.loads(alert.flagDetails) if alert.flagDetails else None,
        resolvedAction=alert.resolvedAction,
        resolvedAt=alert.resolvedAt,
        resolvedById=alert.resolvedById,
        createdAt=alert.createdAt,
        post=AlertPostOut(
            id=post.id,
            caption=post.caption,
            status=post.status,
            flagReason=post.flagReason,
            flaggedAt=post.flaggedAt,
            createdAt=post.createdAt,
            media=[AlertPostMediaOut(url=m.url, order=m.order) for m in (getattr(post, "media", []) or [])],
        ) if post else None,
        comment=AlertCommentOut(  
            id=comment.id,
            body=comment.body,
            createdAt=comment.createdAt,
        ) if comment else None,
        reportedUser=AlertUserOut(
            id=reported_user.id,
            name=reported_user.name,
            email=reported_user.email,
            picture=reported_user.picture,
            designation=reported_user.designation,
        ) if reported_user else None,
        resolvedBy=AlertResolvedByOut(
            id=resolved_by.id,
            name=resolved_by.name,
            email=resolved_by.email,
        ) if resolved_by else None,
    ).model_dump(mode="json")


ALERT_INCLUDE = {
    "post": {"include": {"media": {"order_by": {"order": "asc"}}}},
    "comment": True,
    "reportedUser": True,
    "resolvedBy": True,
}


@alerts_router.get("")
async def list_alerts(
    resolved: Optional[bool] = Query(default=None),
    # auto_removed: Optional[bool] = Query(default=None, alias="autoRemoved"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user=Depends(require_admin),
):
    """
    List alerts.
    - No filters            → all alerts
    - resolved=false        → needs review (resolvedAction IS NULL)
    # - autoRemoved=true      → auto-removed log
    - resolved=true         → admin-resolved (RESTORED or CONFIRMED_REMOVAL)
    """
    where: dict = {}

    if resolved is False:
        where["resolvedAction"] = None
    # elif auto_removed is True:
    #     where["resolvedAction"] = AlertAction.AUTO_REMOVED
    elif resolved is True:
        where["resolvedAction"] = {"in": [AlertAction.RESTORED, AlertAction.CONFIRMED_REMOVAL]}

    total = await db.adminalert.count(where=where)
    alerts = await db.adminalert.find_many(
        where=where,
        include=ALERT_INCLUDE,
        order={"createdAt": "desc"},
        skip=(page - 1) * page_size,
        take=page_size,
    )

    return api_response(200, AlertListResponse(
        alerts=[_serialize_alert(a) for a in alerts],
        total=total,
        page=page,
        pageSize=page_size,
        hasMore=(page * page_size) < total,
    ).model_dump(mode="json"), "Alerts fetched successfully")


@alerts_router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    current_user=Depends(require_admin),
):
    alert = await db.adminalert.find_unique(
        where={"id": alert_id},
        include=ALERT_INCLUDE,
    )
    if not alert:
        raise AppException(404, "Alert not found")

    return api_response(200, _serialize_alert(alert), "Alert fetched successfully")


@alerts_router.patch("/{alert_id}/resolve")
async def resolve_alert_route(
    alert_id: str,
    body: ResolveAlertRequest,
    current_user=Depends(require_admin),
):
    action = (
        AlertAction.RESTORED if body.action == ResolveAlertAction.RESTORE
        else AlertAction.CONFIRMED_REMOVAL
    )

    await resolve_alert(alert_id, action, current_user.id)

    result = ResolveAlertResponse(alertId=alert_id, action=body.action)
    return api_response(200, result.model_dump(mode="json"), "Alert resolved successfully")