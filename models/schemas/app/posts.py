#models/schemas/app/posts.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from prisma.enums import PostType, ContentStatus

# ── Request schemas ───────────────────────────────────────────

class CreatePostRequest(BaseModel):
    caption: Optional[str] = None
    type: PostType = PostType.USER_POST
    media: list["MediaItem"] = []
    taggedUserIds: list[str] = []
    appreciationTypeId: Optional[str] = None # NEW
    recipientIds: list[str] = [] # NEW


class MediaItem(BaseModel):
    url: str
    order: int = 0
    altText: Optional[str] = "Image not found"

class MediaUploadUrlRequest(BaseModel):
    contentType: str = "image/jpeg"


class MediaUploadUrlResponse(BaseModel):
    uploadUrl: str
    publicUrl: str
    path: str
    contentType: str

class UpdatePostRequest(BaseModel):
    caption: Optional[str] = None

class CreateCommentRequest(BaseModel):
    body: str
    parentId: Optional[str] = None
    taggedUserIds: list[str] = []


class UpdateCommentRequest(BaseModel):
    body: str

class LikePostRequest(BaseModel):
    reactionType: Optional[str]= "LIKE"

# ── Response schemas ──────────────────────────────────────────

class MediaOut(BaseModel):
    id: str
    postId: str
    url: str
    order: int
    altText: Optional[str] = None
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)


class TagOut(BaseModel):
    id: str
    taggedUserId: str
    taggedUserName: Optional[str] = None
    taggedUserPicture: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CommentTagOut(BaseModel):
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
    status: ContentStatus
    createdAt: datetime
    updatedAt: datetime
    author: Optional[AuthorOut] = None
    replies: list["CommentOut"] = []
    tags: list[CommentTagOut] = []

    model_config = ConfigDict(from_attributes=True)

# 2. Add AppreciationOut (place this before PostOut)
class AppreciationOut(BaseModel):
    appreciationTypeId: str
    appreciationTypeName: str
    badgePath: str
    description: Optional[str] = None
    recipients: list["TagOut"] = []
    model_config = ConfigDict(from_attributes=True)

class PostOut(BaseModel):
    id: str
    type: PostType
    caption: Optional[str] = None
    status: ContentStatus
    sourceUrl: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    captionEditedAt: Optional[datetime] = None
    authorId: Optional[str] = None
    author: Optional[AuthorOut] = None
    media: list[MediaOut] = []
    tags: list[TagOut] = []
    likeCount: int = 0
    commentCount: int = 0
    isLikedByMe: bool = False
    appreciation: Optional[AppreciationOut] = None # NEW4
    reactionType:Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostDetailOut(PostOut):
    comments: list[CommentOut] = []

class FeedResponse(BaseModel):
    posts: list[PostOut]
    nextCursor: Optional[str] = None
    hasMore: bool 

class LikeResponse(BaseModel):
    postId: str
    liked: bool
    likeCount: int
    reactionType: Optional[str]=None

class DeletePostResponse(BaseModel):
    deletedPostId: str

class DeleteCommentResponse(BaseModel):
    deletedCommentId: str

