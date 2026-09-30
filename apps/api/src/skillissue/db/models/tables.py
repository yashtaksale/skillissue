"""SQLAlchemy models for SkillIssue, per ARCHITECTURE.md §8."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


# ── Enums (matching ARCHITECTURE.md §8) ──────────────────────────────

class ScanStatusEnum(str, enum.Enum):
    QUEUED = "queued"
    CLONING = "cloning"
    SCANNING = "scanning"
    SAMPLING = "sampling"
    ANALYZING = "analyzing"
    SCORING = "scoring"
    FIXING = "fixing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class CoverageKind(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"
    SCANNERS_ONLY = "scanners_only"
    HYGIENE_ONLY = "hygiene_only"


class FindingCategory(str, enum.Enum):
    SECURITY = "security"
    BUGS = "bugs"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    HYGIENE = "hygiene"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingStatusEnum(str, enum.Enum):
    OPEN = "open"
    FIX_SUGGESTED = "fix_suggested"
    FIX_VERIFIED = "fix_verified"
    FIX_FAILED = "fix_failed"
    DISMISSED = "dismissed"


class VerificationStatusEnum(str, enum.Enum):
    NOT_RUN = "not_run"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


# ── Models ───────────────────────────────────────────────────────────

class Repo(Base):
    """Repository metadata."""
    __tablename__ = "repos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True,
                                     server_default=func.gen_random_uuid())
    host: Mapped[str] = mapped_column(Text, nullable=False, default="github.com")
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    github_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    default_branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fork: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_scan_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    scans: Mapped[list["Scan"]] = relationship(back_populates="repo", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("host", "owner", "name", name="repos_host_owner_name_key"),
    )


class Scan(Base):
    """A single scan run."""
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True,
                                     server_default=func.gen_random_uuid())
    repo_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("repos.id"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    branch: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pipeline_version: Mapped[str] = mapped_column(Text, nullable=False, default="0.1.0")
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    options_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ScanStatusEnum] = mapped_column(
        Enum(ScanStatusEnum, name="scan_status", create_constraint=True),
        nullable=False, default=ScanStatusEnum.QUEUED,
    )
    progress_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    coverage: Mapped[CoverageKind | None] = mapped_column(
        Enum(CoverageKind, name="coverage_kind", create_constraint=True),
        nullable=True,
    )
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    subscores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score_inputs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_source_scan_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scans.id"), nullable=True
    )
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("scans_repo_created", "repo_id", created_at.desc()),
        Index("scans_status_heartbeat", "status", "heartbeat_at"),
        Index("scans_expires", "expires_at", postgresql_where=(Column("expires_at").isnot(None))),
    )


class Finding(Base):
    """A single finding from a scan."""
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True,
                                     server_default=func.gen_random_uuid())
    scan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[FindingCategory] = mapped_column(
        Enum(FindingCategory, name="finding_category", create_constraint=True),
        nullable=False,
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, name="finding_severity", create_constraint=True),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.5)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    line_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rule_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sources: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[FindingStatusEnum] = mapped_column(
        Enum(FindingStatusEnum, name="finding_status", create_constraint=True),
        nullable=False, default=FindingStatusEnum.OPEN,
    )
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    roast: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    scan: Mapped["Scan"] = relationship(back_populates="findings")

    __table_args__ = (
        Index("findings_scan_id", "scan_id"),
        Index("findings_fingerprint", "fingerprint"),
    )


class Denylist(Base):
    """Denylist entries for repos/owners."""
    __tablename__ = "denylist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'repo' or 'owner'
    value_lc: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("kind", "value_lc", name="denylist_kind_value_key"),
    )


class ScanEvent(Base):
    """Scan progress events (for SSE replay)."""
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="status")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("scan_events_scan_ts", "scan_id", "ts"),
    )
