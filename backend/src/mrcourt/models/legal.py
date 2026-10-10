import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mrcourt.db.base import Base, IdMixin, TimestampMixin

EMBEDDING_DIMENSIONS = 1024

# Portable column types: PostgreSQL gets the real types, other databases (used in unit tests)
# fall back to JSON/text so the same models work everywhere.
EmbeddingType = JSON().with_variant(Vector(EMBEDDING_DIMENSIONS), "postgresql")
SearchVectorType = Text().with_variant(TSVECTOR(), "postgresql")
JsonType = JSON().with_variant(JSONB(), "postgresql")


class LegalSource(IdMixin, TimestampMixin, Base):
    __tablename__ = "legal_sources"

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    instrument: Mapped[str] = mapped_column(String(300), nullable=False)
    section: Mapped[str | None] = mapped_column(String(30))
    citation_label: Mapped[str] = mapped_column(String(400), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    effective_status: Mapped[str] = mapped_column(String(20), default="in_force", nullable=False)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("legal_sources.id"))
    search_vector: Mapped[str | None] = mapped_column(SearchVectorType)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("knowledge_documents.id"), index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True)  # None = shared
    page: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(60))  # which model made `embedding`
    read_by_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    input_method: Mapped[str] = mapped_column(String(10), default="typed", nullable=False)  # typed | voice
    mode: Mapped[str] = mapped_column(String(10), default="answer", nullable=False)  # answer | assistant | text
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)  # set for Text Assistant entries

    answer: Mapped["Answer"] = relationship(
        back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class Answer(IdMixin, TimestampMixin, Base):
    __tablename__ = "answers"

    question_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("questions.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)  # cited | no_reliable_source
    paragraphs: Mapped[list[dict[str, object]]] = mapped_column(JsonType, default=list)
    disclaimer: Mapped[str] = mapped_column(String(200), nullable=False)
    answer_mode: Mapped[str] = mapped_column(String(10), default="passages", nullable=False)  # full | passages
    steps: Mapped[list[dict[str, object]] | None] = mapped_column(JsonType)

    question: Mapped[Question] = relationship(back_populates="answer")
    citations: Mapped[list["AnswerCitation"]] = relationship(
        cascade="all, delete-orphan", order_by="AnswerCitation.position"
    )


class AnswerCitation(IdMixin, Base):
    __tablename__ = "answer_citations"

    answer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("answers.id"), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("legal_sources.id", ondelete="SET NULL")
    )
    label: Mapped[str | None] = mapped_column(String(400))  # kept when the passage is removed
    source_url: Mapped[str | None] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[LegalSource | None] = relationship()
