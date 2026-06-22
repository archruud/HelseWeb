"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, Text, Date, DateTime,
    ForeignKey, ARRAY, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    entry_date = Column(Date)
    page_number = Column(Integer)
    heading = Column(Text)
    content = Column(Text)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    is_active = Column(Boolean, default=True)
    is_system_admin = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime(timezone=True))

    annotations = relationship("Annotation", back_populates="user")


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    short_name = Column(String(50))
    address = Column(Text)
    city = Column(String(100))
    is_active = Column(Boolean, default=True)
    parent_organization = Column(String(255))
    notes = Column(Text)

    documents = relationship("Document", back_populates="hospital")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_number = Column(String(50))
    title = Column(String(500), nullable=False)
    document_type = Column(String(100))
    category = Column(String(50), default="somatic")
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    department = Column(String(255))
    doctor_name = Column(String(255))
    doctor_approved_by = Column(String(255))

    document_date = Column(Date)
    created_date = Column(DateTime(timezone=True))
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger)
    page_count = Column(Integer)
    ocr_text = Column(Text)
    summary = Column(Text)

    diagnoses = Column(ARRAY(Text))
    procedures = Column(ARRAY(Text))
    keywords = Column(ARRAY(Text))

    # Threading / correspondence
    thread_id = Column(UUID(as_uuid=True), ForeignKey("document_threads.id"))
    parent_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    sender = Column(Text)
    recipient = Column(Text)
    is_reply = Column(Boolean, default=False)
    correspondence_key = Column(Text)
    content_hash = Column(Text)
    ai_indexed = Column(Boolean, default=False)

    is_verified = Column(Boolean, default=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital = relationship("Hospital", back_populates="documents")
    annotations = relationship("Annotation", back_populates="document", cascade="all, delete-orphan")
    thread = relationship("DocumentThread", back_populates="documents")


class DocumentThread(Base):
    __tablename__ = "document_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500))
    description = Column(Text)
    start_date = Column(Date)
    end_date = Column(Date)
    thread_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    documents = relationship("Document", back_populates="thread")


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    annotation_type = Column(String(50), default="note")
    content = Column(Text, nullable=False)
    page_number = Column(Integer)
    is_private = Column(Boolean, default=False)
    visibility = Column(String(50), default="all")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="annotations")
    user = relationship("User", back_populates="annotations")


class PrivateFile(Base):
    __tablename__ = "private_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    file_type = Column(String(50))
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger)
    duration_seconds = Column(Integer)
    transcript = Column(Text)
    related_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    related_date = Column(Date)
    visibility = Column(String(50), default="admin_only")
    allowed_roles = Column(ARRAY(Text))
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    event_date = Column(Date, nullable=False)
    end_date = Column(Date)
    event_type = Column(String(50))
    severity = Column(String(20), default="normal")
    hospital_id = Column(Integer, ForeignKey("hospitals.id"))
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    source_document_ids = Column(ARRAY(UUID(as_uuid=True)))
    auto_generated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(UUID(as_uuid=True))
    details = Column(JSONB)
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
