from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserRole(str, Enum):
    employee = "employee"
    manager = "manager"


class TicketStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"


class ActorType(str, Enum):
    user = "user"
    system = "system"
    ai = "ai"


class TicketHistoryEventType(str, Enum):
    ticket_created = "ticket_created"
    group_assigned = "group_assigned"
    group_status_changed = "group_status_changed"
    manager_comment_updated = "manager_comment_updated"


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    fullName: str
    initials: str
    role: UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AuthTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessToken: str
    tokenType: str
    expiresIn: int
    user: User


class Actor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActorType
    id: str | None = None
    displayName: str


class TicketHistoryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: TicketHistoryEventType
    label: str
    fromStatus: TicketStatus | None = None
    toStatus: TicketStatus | None = None
    createdAt: datetime
    actor: Actor


class Ticket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    number: str
    title: str
    description: str
    originalDescription: str | None = None
    aiEnhanced: bool
    status: TicketStatus
    managerComment: str | None = None
    author: User
    groupId: str | None = None
    createdAt: datetime
    updatedAt: datetime
    resolvedAt: datetime | None = None
    history: list[TicketHistoryEvent]


class TicketAuthorSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fullName: str
    initials: str


class RelatedTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticketId: str
    authorSummary: TicketAuthorSummary
    descriptionExcerpt: str
    createdAt: datetime
    aiEnhanced: bool
    status: TicketStatus


class TicketGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    aiSummary: str
    status: TicketStatus
    ticketCount: int = Field(ge=0)
    lastTicketCreatedAt: datetime
    managerComment: str | None = None
    relatedTickets: list[RelatedTicket]
    createdAt: datetime
    updatedAt: datetime


class EnhanceTicketDescriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    originalText: str = Field(min_length=1, max_length=10000)


class EnhanceTicketDescriptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    originalText: str
    enhancedText: str
    aiEnhanced: bool = True
    displayPrefix: str


class CreateTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    originalDescription: str | None = Field(default=None, max_length=10000)
    aiEnhanced: bool

    @model_validator(mode="after")
    def validate_original_description(self):
        if self.aiEnhanced and not self.originalDescription:
            raise ValueError("originalDescription is required when aiEnhanced is true")
        return self


class UpdateTicketGroupStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TicketStatus


class SaveTicketGroupCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    managerComment: str = Field(min_length=1, max_length=5000)


class PaginationMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)
    totalItems: int = Field(ge=0)
    totalPages: int = Field(ge=0)
    hasNextPage: bool
    hasPreviousPage: bool


class MyTicketsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Ticket]
    meta: PaginationMeta


class TicketGroupListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TicketGroup]
    meta: PaginationMeta


class StatusCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: int = Field(ge=0)
    in_review: int = Field(ge=0)
    resolved: int = Field(ge=0)


class TopRepeatedProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groupId: str
    title: str
    ticketCount: int = Field(ge=0)
    status: TicketStatus
    lastTicketCreatedAt: datetime


class ManagerAnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groupsByStatus: StatusCount
    ticketsByStatus: StatusCount
    topRepeatedProblems: list[TopRepeatedProblem]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    issue: str


class ErrorObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: list[ErrorDetail]
    requestId: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorObject
