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
    appreciationTypeId: Optional[str] = None 
    recipientIds: list[str] = [] 
    pollOptions: list[str]=[]         # NEW — required for type=POLL, 2-5 entries
    pollClosesAt: Optional[datetime] = None  # NEW — optional deadline, must be in the future


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
    pollOptions:Optional[list[str]] = None # NEW — only for editing a poll's option text;
                                                   # must match the existing option count exactly,
                                                   # adding/removing options is not supported
    taggedUserIds: Optional[list[str]] = None  # NEW — full replacement list;
                                               # None = no change, [] = remove all tags


class CreateCommentRequest(BaseModel):
    body: str
    parentId: Optional[str] = None
    taggedUserIds: list[str] = []


class UpdateCommentRequest(BaseModel):
    body: str

class LikePostRequest(BaseModel):
    reactionType: Optional[str]= "LIKE"

class CastVoteRequest(BaseModel):
    optionId:str

class ExtendPollRequest(BaseModel):
    newClosesAt: datetime

class PollVoterOut(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class PollOptionVotersOut(BaseModel):
    id: str
    text: str
    order: int
    voteCount: int = 0
    voters: list[PollVoterOut] = []

    model_config = ConfigDict(from_attributes=True)

class PollVotersResponse(BaseModel):
    postId: str
    pollId: str
    options: list[PollOptionVotersOut] = []

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

# NEW - poll response models 
class PollOptionOut(BaseModel):
    id:str 
    text:str
    order:int
    voteCount: int = 0

    model_config = ConfigDict(from_attributes=True)

class PollOut(BaseModel): 
    id:str 
    closesAt: Optional[datetime] = None
    isManuallyClosed: bool = False
    manuallyClosedAt: Optional[datetime] = None
    isOpen: bool = True
    totalVotes: int = 0
    userVoteOptionId: Optional[str] = None
    options: list[PollOptionOut] = []

    model_config = ConfigDict(from_attributes=True)

class PostLinkMetadata(BaseModel):
    """
    Metadata for a single URL found in a post caption, fetched on-the-fly.

    Future scope (TODO): once we have a PostLink DB table that stores this at
    post-creation time, this will be populated from a DB join (like media/tags)
    instead of a live HTTP fetch, making reads free.
    """
    url: str
    title: Optional[str] = None  # None if fetch failed — frontend falls back to raw URL


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
    appreciation: Optional[AppreciationOut] = None # NEW
    poll: Optional[PollOut] = None
    reactionType:Optional[str] = None
    linkMetadata: list[PostLinkMetadata] = []

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

