from typing import Literal
from pydantic import BaseModel, Field

Intent = Literal["Knowledge Question", "Incident", "Service Request", "Automatable Issue"]
Priority = Literal["P1", "P2", "P3", "P4"]

class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)
    user_id: str = "demo.employee"
    conversation_id: str | None = None
    create_ticket: bool = False

class TicketCreate(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    user_id: str = "demo.employee"
    idempotency_key: str | None = None

class TicketUpdate(BaseModel):
    state: str | None = None
    priority: Priority | None = None
    assigned_group: str | None = None
    notes: str | None = None

class AutomationRequest(BaseModel):
    ticket_id: str | None = None
    issue: str = Field(min_length=3, max_length=2000)
    action: str | None = None
    authorized: bool = False
    approval_granted: bool = False

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)

class SoftwareRequestCreate(BaseModel):
    software_id: str
    user_id: str = "demo.employee"
    business_justification: str = Field(default="Required for work", max_length=1000)

class ResolveRequest(BaseModel):
    resolution_notes: str = "Resolved through approved workflow."
