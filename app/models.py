from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="user", server_default="user")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    reports = relationship("Report", back_populates="user")
    uploaded_evidence = relationship("EvidenceRecord", back_populates="uploader")


class Report(Base):
    """A citizen or officer report; description stores authenticated ciphertext."""

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter = Column(String(64), nullable=False)
    location = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="submitted", server_default="submitted")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="reports")
    evidence = relationship("EvidenceRecord", back_populates="report")


class EvidenceRecord(Base):
    """Metadata for a private object stored in Google Cloud Storage."""

    __tablename__ = "evidence_records"

    id = Column(String(36), primary_key=True)
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="RESTRICT"), nullable=False, index=True)
    object_name = Column(String(1024), unique=True, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(String(127), nullable=False)
    original_filename = Column(String(255), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    report = relationship("Report", back_populates="evidence")
    uploader = relationship("User", back_populates="uploaded_evidence")
