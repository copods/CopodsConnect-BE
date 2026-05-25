from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


# ── Request schemas ───────────────────────────────────────────

class CreatePostRequest(BaseModel):
    caption: Optional[str] = None
    type: str = "USER_POST"
    media: list["MediaItem"] = []
    taggedUserIds: list[str] = []


class MediaItem(BaseModel):
    url: str
    order: int = 0
    altText: Optional[str] = None


class UpdatePostRequest(BaseModel):
    caption: Optional[str] = None


class CreateCommentRequest(BaseModel):
    body: str
    parentId: Optional[str] = None


class UpdateCommentRequest(BaseModel):
    body: str


# ── Response schemas ──────────────────────────────────────────

class MediaOut(BaseModel):
    id: str
    url: str
    order: int
    altText: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TagOut(BaseModel):
    id: str
    taggedUserId: str
    taggedUserName: Optional[str] = None
    taggedUserPicture: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuthorOut(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None
    designation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CommentOut(BaseModel):
    id: str
    body: str
    authorId: str
    parentId: Optional[str] = None
    status: str
    createdAt: datetime
    updatedAt: datetime
    author: Optional[AuthorOut] = None
    replies: list["CommentOut"] = []

    model_config = ConfigDict(from_attributes=True)


class PostOut(BaseModel):
    id: str
    type: str
    caption: Optional[str] = None
    status: str
    sourceUrl: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    authorId: Optional[str] = None
    author: Optional[AuthorOut] = None
    media: list[MediaOut] = []
    tags: list[TagOut] = []
    likeCount: int = 0
    commentCount: int = 0
    isLikedByMe: bool = False

    model_config = ConfigDict(from_attributes=True)


class PostDetailOut(PostOut):
    comments: list[CommentOut] = []
