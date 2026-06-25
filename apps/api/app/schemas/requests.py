from pydantic import BaseModel, Field


class CleaningRequest(BaseModel):
    actions: list[str] = Field(default_factory=list)


class RollbackRequest(BaseModel):
    version: int


class ChatRequest(BaseModel):
    question: str


class CopilotRequest(BaseModel):
    message: str


class ExportPDFRequest(BaseModel):
    message_id: str | None = None
    messages: list[dict] | None = None

