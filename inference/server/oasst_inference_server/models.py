import datetime
import enum
from uuid import uuid4

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from oasst_inference_server.schemas import chat as chat_schema
from oasst_shared.schemas import inference
from sqlmodel import Field, Index, Relationship, SQLModel


class DbMessage(SQLModel, table=True):
    __tablename__ = "message"

    role: str = Field(index=True)
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    chat: "DbChat" = Relationship(back_populates="messages")
    reports: list["DbReport"] = Relationship(back_populates="message")

    parent_id: str | None = Field(None)

    content: str | None = Field(None)
    error: str | None = Field(None)

    state: inference.MessageState = Field(inference.MessageState.manual)
    work_parameters: inference.WorkParameters = Field(None, sa_column=sa.Column(pg.JSONB))
    work_begin_at: datetime.datetime | None = Field(None)
    work_end_at: datetime.datetime | None = Field(None)
    worker_id: str | None = Field(None, foreign_key="worker.id")
    worker_compat_hash: str | None = Field(None, index=True)
    worker_config: inference.WorkerConfig | None = Field(None, sa_column=sa.Column(pg.JSONB))

    score: int = Field(0)

    def to_read(self) -> inference.MessageRead:
        return inference.MessageRead(
            id=self.id,
            content=self.content,
            role=self.role,
            state=self.state,
            score=self.score,
            reports=[r.to_read() for r in self.reports],
        )


class DbChat(SQLModel, table=True):
    __tablename__ = "chat"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    user_id: str = Field(foreign_key="user.id", index=True)

    messages: list[DbMessage] = Relationship(back_populates="chat")

    def to_list_read(self) -> chat_schema.ChatListRead:
        return chat_schema.ChatListRead(id=self.id)

    def to_read(self) -> chat_schema.ChatRead:
        return chat_schema.ChatRead(id=self.id, messages=[m.to_read() for m in self.messages])

    def get_msg_dict(self) -> dict[str, DbMessage]:
        return {m.id: m for m in self.messages}


class DbReport(SQLModel, table=True):
    __tablename__ = "report"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    message_id: str = Field(..., foreign_key="message.id", index=True)
    message: DbMessage = Relationship(back_populates="reports")
    report_type: inference.ReportType = Field(...)
    reason: str = Field(...)

    def to_read(self) -> inference.Report:
        return inference.Report(id=self.id, report_type=self.report_type, reason=self.reason)


class WorkerEventType(str, enum.Enum):
    connect = "connect"


class DbWorkerEvent(SQLModel, table=True):
    __tablename__ = "worker_event"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    worker_id: str = Field(foreign_key="worker.id", index=True)
    worker: "DbWorker" = Relationship(back_populates="events")
    time: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    event_type: WorkerEventType
    worker_config: inference.WorkerConfig | None = Field(None, sa_column=sa.Column(pg.JSONB))


class DbWorker(SQLModel, table=True):
    __tablename__ = "worker"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    api_key: str = Field(default_factory=lambda: str(uuid4()), index=True)
    name: str

    in_compliance_check: bool = Field(default=False, sa_column=sa.Column(sa.Boolean, server_default=sa.text("false")))
    next_compliance_check: datetime.datetime | None = Field(None)
    events: list[DbWorkerEvent] = Relationship(back_populates="worker")


class DbUser(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = (Index("provider", "provider_account_id", unique=True),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    provider: str = Field(index=True)
    provider_account_id: str = Field(index=True)

    display_name: str = Field(nullable=False, max_length=256)
