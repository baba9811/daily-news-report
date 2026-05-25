"""SQLAlchemy ORM models with entity conversion methods."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from daily_scheduler.database import Base
from daily_scheduler.domain.entities.price import (
    PriceSnapshot as PriceEntity,
)
from daily_scheduler.domain.entities.recommendation import (
    Recommendation as RecEntity,
)
from daily_scheduler.domain.entities.report import (
    Report as ReportEntity,
)
from daily_scheduler.domain.entities.retrospective import (
    Retrospective as RetroEntity,
)
from daily_scheduler.domain.entities.retrospective import (
    WeeklyAnalysis as WeeklyEntity,
)
from daily_scheduler.tz import localize as _localize


class ReportModel(Base):
    """SQLAlchemy model for reports."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    report_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(default="daily")
    html_content: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    prompt_used: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    raw_response: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    generation_time_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    recommendations: Mapped[list[RecommendationModel]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )

    def to_entity(self) -> ReportEntity:
        """Convert to domain entity."""
        return ReportEntity(
            id=self.id,
            report_date=self.report_date,
            report_type=self.report_type,
            html_content=self.html_content,
            summary=self.summary,
            prompt_used=self.prompt_used,
            raw_response=self.raw_response,
            generation_time_s=self.generation_time_s,
            created_at=_localize(self.created_at),
        )

    @staticmethod
    def from_entity(entity: ReportEntity) -> ReportModel:
        """Create model from domain entity."""
        model = ReportModel(
            report_date=entity.report_date,
            report_type=entity.report_type,
            html_content=entity.html_content,
            summary=entity.summary,
            prompt_used=entity.prompt_used,
            raw_response=entity.raw_response,
            generation_time_s=entity.generation_time_s,
        )
        if entity.id is not None:
            model.id = entity.id
        return model


class RecommendationModel(Base):
    """SQLAlchemy model for recommendations."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reports.id"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(nullable=False)
    market: Mapped[str] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(nullable=False)
    timeframe: Mapped[str] = mapped_column(nullable=False)
    entry_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    target_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    stop_loss: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    rationale: Mapped[str] = mapped_column(Text, default="")
    sector: Mapped[str] = mapped_column(default="")
    current_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        default="OPEN",
        index=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    closed_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    pnl_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    debate_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )
    memory_node_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    report: Mapped[ReportModel] = relationship(
        back_populates="recommendations",
    )

    def to_entity(self) -> RecEntity:
        """Convert to domain entity."""
        return RecEntity(
            id=self.id,
            report_id=self.report_id,
            ticker=self.ticker,
            name=self.name,
            market=self.market,
            direction=self.direction,
            timeframe=self.timeframe,
            entry_price=self.entry_price,
            target_price=self.target_price,
            stop_loss=self.stop_loss,
            rationale=self.rationale,
            sector=self.sector,
            current_price=self.current_price,
            status=self.status,
            closed_at=_localize(self.closed_at) if self.closed_at else None,
            closed_price=self.closed_price,
            pnl_percent=self.pnl_percent,
            created_at=_localize(self.created_at),
        )

    @staticmethod
    def from_entity(entity: RecEntity) -> RecommendationModel:
        """Create model from domain entity."""
        model = RecommendationModel(
            report_id=entity.report_id,
            ticker=entity.ticker,
            name=entity.name,
            market=entity.market,
            direction=entity.direction,
            timeframe=entity.timeframe,
            entry_price=entity.entry_price,
            target_price=entity.target_price,
            stop_loss=entity.stop_loss,
            rationale=entity.rationale,
            sector=entity.sector,
            current_price=entity.current_price,
            status=entity.status,
            closed_at=entity.closed_at,
            closed_price=entity.closed_price,
            pnl_percent=entity.pnl_percent,
        )
        if entity.id is not None:
            model.id = entity.id
        return model


class PriceSnapshotModel(Base):
    """SQLAlchemy model for price snapshots."""

    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "snapshot_date",
            name="uq_ticker_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    ticker: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    open_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    high: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    low: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    volume: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    def to_entity(self) -> PriceEntity:
        """Convert to domain entity."""
        return PriceEntity(
            id=self.id,
            ticker=self.ticker,
            snapshot_date=self.snapshot_date,
            price=self.price,
            open_price=self.open_price,
            high=self.high,
            low=self.low,
            volume=self.volume,
            created_at=_localize(self.created_at),
        )

    @staticmethod
    def from_entity(
        entity: PriceEntity,
    ) -> PriceSnapshotModel:
        """Create model from domain entity."""
        model = PriceSnapshotModel(
            ticker=entity.ticker,
            snapshot_date=entity.snapshot_date,
            price=entity.price,
            open_price=entity.open_price,
            high=entity.high,
            low=entity.low,
            volume=entity.volume,
        )
        if entity.id is not None:
            model.id = entity.id
        return model


class RetrospectiveModel(Base):
    """SQLAlchemy model for retrospectives."""

    __tablename__ = "retrospectives"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    report_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        unique=True,
    )
    recommendations_checked: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    targets_hit: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    stops_hit: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    expired_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    context_block: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    def to_entity(self) -> RetroEntity:
        """Convert to domain entity."""
        return RetroEntity(
            id=self.id,
            report_date=self.report_date,
            recommendations_checked=(self.recommendations_checked),
            targets_hit=self.targets_hit,
            stops_hit=self.stops_hit,
            expired_count=self.expired_count,
            context_block=self.context_block,
            created_at=_localize(self.created_at),
        )

    @staticmethod
    def from_entity(
        entity: RetroEntity,
    ) -> RetrospectiveModel:
        """Create model from domain entity."""
        model = RetrospectiveModel(
            report_date=entity.report_date,
            recommendations_checked=(entity.recommendations_checked),
            targets_hit=entity.targets_hit,
            stops_hit=entity.stops_hit,
            expired_count=entity.expired_count,
            context_block=entity.context_block,
        )
        if entity.id is not None:
            model.id = entity.id
        return model


class WeeklyAnalysisModel(Base):
    """SQLAlchemy model for weekly analyses."""

    __tablename__ = "weekly_analyses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    week_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    week_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    total_recommendations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    win_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    loss_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    avg_return_pct: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    best_pick_ticker: Mapped[str] = mapped_column(
        default="",
    )
    worst_pick_ticker: Mapped[str] = mapped_column(
        default="",
    )
    sector_breakdown: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )
    analysis_text: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    lessons: Mapped[str] = mapped_column(
        Text,
        default="[]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    def to_entity(self) -> WeeklyEntity:
        """Convert to domain entity."""
        return WeeklyEntity(
            id=self.id,
            week_start=self.week_start,
            week_end=self.week_end,
            total_recommendations=(self.total_recommendations),
            win_count=self.win_count,
            loss_count=self.loss_count,
            avg_return_pct=self.avg_return_pct,
            best_pick_ticker=self.best_pick_ticker,
            worst_pick_ticker=self.worst_pick_ticker,
            sector_breakdown=self.sector_breakdown,
            analysis_text=self.analysis_text,
            lessons=self.lessons,
            created_at=_localize(self.created_at),
        )

    @staticmethod
    def from_entity(
        entity: WeeklyEntity,
    ) -> WeeklyAnalysisModel:
        """Create model from domain entity."""
        model = WeeklyAnalysisModel(
            week_start=entity.week_start,
            week_end=entity.week_end,
            total_recommendations=(entity.total_recommendations),
            win_count=entity.win_count,
            loss_count=entity.loss_count,
            avg_return_pct=entity.avg_return_pct,
            best_pick_ticker=entity.best_pick_ticker,
            worst_pick_ticker=entity.worst_pick_ticker,
            sector_breakdown=entity.sector_breakdown,
            analysis_text=entity.analysis_text,
            lessons=entity.lessons,
        )
        if entity.id is not None:
            model.id = entity.id
        return model


# --- Multi-agent council ORM (Plan 2) ---


class AgentBindingModel(Base):
    """SQLAlchemy model for agent role overrides (role -> backend binding)."""

    __tablename__ = "agent_binding"

    role: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    system_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DebateModel(Base):
    """SQLAlchemy model for a debate run."""

    __tablename__ = "debate"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pipeline: Mapped[str] = mapped_column(String, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String, nullable=False)
    verdict_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RoundModel(Base):
    """SQLAlchemy model for a single debate round + judge scoring."""

    __tablename__ = "round"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    debate_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("debate.id"),
        nullable=False,
        index=True,
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_score: Mapped[float] = mapped_column(Float, nullable=False)
    llm_score: Mapped[float] = mapped_column(Float, nullable=False)
    false_consensus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    converged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dimensions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    next_round_questions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SpeechModel(Base):
    """SQLAlchemy model for an individual agent speech inside a round."""

    __tablename__ = "speech"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    debate_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("debate.id"),
        nullable=False,
        index=True,
    )
    round_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("round.id"),
        nullable=True,
        index=True,
    )
    agent_role: Mapped[str] = mapped_column(String, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cli_command_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
