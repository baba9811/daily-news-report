"""Dependency injection — factory functions that wire adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from daily_scheduler.application.use_cases.build_retrospective import (
    BuildRetrospective,
)
from daily_scheduler.application.use_cases.check_recommendations import (
    CheckRecommendations,
)
from daily_scheduler.application.use_cases.run_daily_pipeline import (
    RunDailyPipeline,
)
from daily_scheduler.application.use_cases.run_news_pipeline import (
    RunNewsBriefingPipeline,
)
from daily_scheduler.application.use_cases.run_weekly_pipeline import (
    RunWeeklyPipeline,
)
from daily_scheduler.application.use_cases.update_prices import (
    UpdatePrices,
)
from daily_scheduler.config import get_settings
from daily_scheduler.constants import MAX_CONCURRENT_LLM_CALLS
from daily_scheduler.domain.ports.multica import MulticaPort
from daily_scheduler.infrastructure.adapters.council.council_news_provider import (
    CouncilNewsProvider,
)
from daily_scheduler.infrastructure.adapters.debate.in_memory_debate_bus import (
    InMemoryDebateBus,
)
from daily_scheduler.infrastructure.adapters.debate.llm_router import LLMRouter
from daily_scheduler.infrastructure.adapters.email.smtp_sender import (
    SmtpEmailSender,
)
from daily_scheduler.infrastructure.adapters.finance.yfinance_provider import (
    YFinanceProvider,
)
from daily_scheduler.infrastructure.adapters.llm.claude_code_provider import (
    ClaudeCodeProvider,
)
from daily_scheduler.infrastructure.adapters.llm.codex_provider import CodexProvider
from daily_scheduler.infrastructure.adapters.llm.subprocess_pool import SubprocessPool
from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
    JSONTreeIndex,
)
from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
    MarkdownMemoryStore,
)
from daily_scheduler.infrastructure.adapters.memory.memory_store import MemoryStore
from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
    SQLiteFTS5Search,
)
from daily_scheduler.infrastructure.adapters.multica.http_client import (
    MulticaHTTPClient,
)
from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
    SQLAlchemyAgentBindingRepository,
)
from daily_scheduler.infrastructure.adapters.persistence.debate_repository import (
    SQLAlchemyDebateRepository,
)
from daily_scheduler.infrastructure.adapters.persistence.price_repository import (
    SQLAlchemyPriceRepository,
)
from daily_scheduler.infrastructure.adapters.persistence.recommendation_repository import (
    SQLAlchemyRecommendationRepository,
)
from daily_scheduler.infrastructure.adapters.persistence.report_repository import (
    SQLAlchemyReportRepository,
)
from daily_scheduler.infrastructure.adapters.persistence.retrospective_repository import (
    SQLAlchemyRetrospectiveRepository,
)
from daily_scheduler.infrastructure.adapters.template.renderer import (
    Jinja2ReportRenderer,
)


def get_retro_repo(
    db: Session,
) -> SQLAlchemyRetrospectiveRepository:
    """Create a retrospective repository."""
    return SQLAlchemyRetrospectiveRepository(db)


def get_report_repo(
    db: Session,
) -> SQLAlchemyReportRepository:
    """Create a report repository."""
    return SQLAlchemyReportRepository(db)


def get_rec_repo(
    db: Session,
) -> SQLAlchemyRecommendationRepository:
    """Create a recommendation repository."""
    return SQLAlchemyRecommendationRepository(db)


def get_price_repo(
    db: Session,
) -> SQLAlchemyPriceRepository:
    """Create a price repository."""
    return SQLAlchemyPriceRepository(db)


def get_finance_provider() -> YFinanceProvider:
    """Create a finance provider."""
    return YFinanceProvider()


def get_agent_binding_repo(
    db: Session,
) -> SQLAlchemyAgentBindingRepository:
    """Create an agent_binding repository."""
    return SQLAlchemyAgentBindingRepository(db)


def get_debate_repo(
    db: Session,
) -> SQLAlchemyDebateRepository:
    """Create a debate repository."""
    return SQLAlchemyDebateRepository(db)


def get_news_provider(
    *,
    session_factory: Callable[[], Session],
    engine: Engine,
    memory_root: Path,
) -> CouncilNewsProvider:
    """Build the multi-agent CouncilNewsProvider.

    Plan 2 replaces the legacy ClaudeNewsProvider here. The four pipeline
    methods retain their signatures, so the existing pipeline use cases
    continue to work unchanged.
    """
    memory_store = get_memory_store(
        session_factory=session_factory,
        engine=engine,
        memory_root=memory_root,
    )
    # Binding + debate repos use short-lived sessions bound to the same engine
    # so that runtime overrides and persisted debates are visible across calls.
    binding_session = session_factory()
    binding_repo = SQLAlchemyAgentBindingRepository(binding_session)
    debate_session = session_factory()
    debate_repo = SQLAlchemyDebateRepository(debate_session)
    router = LLMRouter(
        claude_code=get_claude_code_provider(),
        codex=get_codex_provider(),
        binding_repo=binding_repo,
    )
    settings = get_settings()
    multica: MulticaPort | None = None
    if settings.multica_base_url:
        multica = MulticaHTTPClient(base_url=settings.multica_base_url)
    return CouncilNewsProvider(
        router=router,
        memory_store=memory_store,
        debate_repo=debate_repo,
        bus=get_debate_bus(),
        multica=multica,
    )


def get_email_sender() -> SmtpEmailSender:
    """Create an email sender."""
    return SmtpEmailSender(get_settings())


def get_renderer() -> Jinja2ReportRenderer:
    """Create a report renderer."""
    return Jinja2ReportRenderer()


def _derive_session_context(
    db: Session,
) -> tuple[Callable[[], Session], Engine, Path]:
    """Build (session_factory, engine, memory_root) from an active Session."""
    bind = db.get_bind()
    if not isinstance(bind, Engine):  # pragma: no cover — defensive
        raise RuntimeError("Active session is not bound to an Engine")
    factory = sessionmaker(bind=bind, autocommit=False, autoflush=False)
    settings = get_settings()
    memory_root = settings.db_path.parent / "memory"
    return factory, bind, memory_root


def get_daily_pipeline(db: Session) -> RunDailyPipeline:
    """Wire all adapters into the daily pipeline use case."""
    session_factory, engine, memory_root = _derive_session_context(db)
    memory_store = get_memory_store(
        session_factory=session_factory,
        engine=engine,
        memory_root=memory_root,
    )
    return RunDailyPipeline(
        report_repo=get_report_repo(db),
        rec_repo=get_rec_repo(db),
        retro_repo=get_retro_repo(db),
        price_repo=get_price_repo(db),
        finance=get_finance_provider(),
        news=get_news_provider(
            session_factory=session_factory,
            engine=engine,
            memory_root=memory_root,
        ),
        email=get_email_sender(),
        renderer=get_renderer(),
        memory_store=memory_store,
    )


def get_weekly_pipeline(
    db: Session,
) -> RunWeeklyPipeline:
    """Wire all adapters into the weekly pipeline use case."""
    session_factory, engine, memory_root = _derive_session_context(db)
    return RunWeeklyPipeline(
        report_repo=get_report_repo(db),
        rec_repo=get_rec_repo(db),
        news=get_news_provider(
            session_factory=session_factory,
            engine=engine,
            memory_root=memory_root,
        ),
        email=get_email_sender(),
    )


def get_update_prices(db: Session) -> UpdatePrices:
    """Wire adapters into the update prices use case."""
    return UpdatePrices(
        rec_repo=get_rec_repo(db),
        price_repo=get_price_repo(db),
        finance=get_finance_provider(),
    )


def get_check_recommendations(
    db: Session,
) -> CheckRecommendations:
    """Wire adapters into the check recommendations use case."""
    session_factory, engine, memory_root = _derive_session_context(db)
    memory_store = get_memory_store(
        session_factory=session_factory,
        engine=engine,
        memory_root=memory_root,
    )
    return CheckRecommendations(
        rec_repo=get_rec_repo(db),
        finance=get_finance_provider(),
        memory_store=memory_store,
    )


def get_news_pipeline(db: Session) -> RunNewsBriefingPipeline:
    """Wire adapters into the Korean news briefing pipeline use case."""
    session_factory, engine, memory_root = _derive_session_context(db)
    news_provider = get_news_provider(
        session_factory=session_factory,
        engine=engine,
        memory_root=memory_root,
    )
    return RunNewsBriefingPipeline(
        report_repo=get_report_repo(db),
        generate_briefing=news_provider.generate_news_briefing,
        email=get_email_sender(),
        report_type="news",
        email_subject_label="Korean News Briefing",
        html_filename_suffix="news",
        renderer=get_renderer(),
    )


def get_global_news_pipeline(db: Session) -> RunNewsBriefingPipeline:
    """Wire adapters into the global news briefing pipeline use case."""
    session_factory, engine, memory_root = _derive_session_context(db)
    news_provider = get_news_provider(
        session_factory=session_factory,
        engine=engine,
        memory_root=memory_root,
    )
    return RunNewsBriefingPipeline(
        report_repo=get_report_repo(db),
        generate_briefing=news_provider.generate_global_news_briefing,
        email=get_email_sender(),
        report_type="global_news",
        email_subject_label="Global News Briefing",
        html_filename_suffix="global_news",
        renderer=get_renderer(),
    )


def get_build_retrospective(
    db: Session,
) -> BuildRetrospective:
    """Wire adapters into the build retrospective use case."""
    return BuildRetrospective(
        rec_repo=get_rec_repo(db),
    )


# --- Multi-agent council factories (Plan 1) ---

_subprocess_pool: SubprocessPool | None = None  # pylint: disable=invalid-name
_debate_bus: InMemoryDebateBus | None = None  # pylint: disable=invalid-name


def get_subprocess_pool() -> SubprocessPool:
    """Process-wide singleton subprocess pool."""
    global _subprocess_pool  # noqa: PLW0603  pylint: disable=global-statement
    if _subprocess_pool is None:
        _subprocess_pool = SubprocessPool(max_concurrent=MAX_CONCURRENT_LLM_CALLS)
    return _subprocess_pool


def get_debate_bus() -> InMemoryDebateBus:
    """Process-wide singleton debate event bus (pub/sub)."""
    global _debate_bus  # noqa: PLW0603  pylint: disable=global-statement
    if _debate_bus is None:
        _debate_bus = InMemoryDebateBus()
    return _debate_bus


def get_claude_code_provider() -> ClaudeCodeProvider:
    """Create the Claude Code CLI LLM provider."""
    settings = get_settings()
    return ClaudeCodeProvider(
        pool=get_subprocess_pool(),
        cli_path=settings.claude_cli_path,
    )


def get_codex_provider() -> CodexProvider:
    """Create the Codex CLI LLM provider."""
    settings = get_settings()
    return CodexProvider(
        pool=get_subprocess_pool(),
        cli_path=settings.codex_cli_path,
    )


def get_memory_store(
    session_factory: Callable[[], Session],
    engine: Engine,
    memory_root: Path,
) -> MemoryStore:
    """Wire the composite MemoryStore (markdown + JSON tree + FTS5)."""
    markdown = MarkdownMemoryStore(root=memory_root)
    tree = JSONTreeIndex(
        session_factory=session_factory,
        tree_path=memory_root / "tree.json",
    )
    fts = SQLiteFTS5Search(engine=engine)
    return MemoryStore(
        markdown=markdown,
        tree=tree,
        fts=fts,
        session_factory=session_factory,
    )


def get_memory_store_for_request(db: Session) -> MemoryStore:
    """Build a request-scoped MemoryStore bound to the active Session's engine."""
    session_factory, engine, memory_root = _derive_session_context(db)
    return get_memory_store(
        session_factory=session_factory,
        engine=engine,
        memory_root=memory_root,
    )
