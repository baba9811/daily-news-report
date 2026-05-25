"""SQLAlchemy implementation of RecommendationRepositoryPort."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from daily_scheduler.domain.entities.recommendation import (
    Recommendation,
)
from daily_scheduler.domain.ports.recommendation_repository import (
    RecommendationRepositoryPort,
)
from daily_scheduler.infrastructure.adapters.persistence.models import (
    RecommendationModel,
)


class SQLAlchemyRecommendationRepository(
    RecommendationRepositoryPort,
):
    """Persist recommendations via SQLAlchemy."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_open(self) -> list[Recommendation]:
        models = (
            self._db.query(RecommendationModel).filter(RecommendationModel.status == "OPEN").all()
        )
        return [m.to_entity() for m in models]

    def get_by_period(
        self,
        since: datetime,
    ) -> list[Recommendation]:
        models = (
            self._db.query(RecommendationModel)
            .filter(
                RecommendationModel.created_at >= since,
            )
            .all()
        )
        return [m.to_entity() for m in models]

    def get_closed_by_period(
        self,
        since: datetime,
    ) -> list[Recommendation]:
        models = (
            self._db.query(RecommendationModel)
            .filter(
                RecommendationModel.created_at >= since,
                RecommendationModel.status.in_(
                    ["TARGET_HIT", "STOP_HIT"],
                ),
            )
            .all()
        )
        return [m.to_entity() for m in models]

    def save(self, rec: Recommendation) -> Recommendation:
        model = RecommendationModel.from_entity(rec)
        self._db.add(model)
        self._db.flush()
        self._db.commit()
        return model.to_entity()

    def save_many(
        self,
        recs: list[Recommendation],
    ) -> list[Recommendation]:
        models = [RecommendationModel.from_entity(r) for r in recs]
        self._db.add_all(models)
        self._db.flush()
        self._db.commit()
        return [m.to_entity() for m in models]

    def update(self, rec: Recommendation) -> None:
        model = self._db.query(RecommendationModel).filter(RecommendationModel.id == rec.id).first()
        if model is None:
            return

        model.current_price = rec.current_price
        model.status = rec.status
        model.closed_at = rec.closed_at
        model.closed_price = rec.closed_price
        model.pnl_percent = rec.pnl_percent
        model.debate_id = rec.debate_id
        model.memory_node_id = rec.memory_node_id
        self._db.commit()

    def list_all(
        self,
        status: str = "all",
        limit: int = 100,
    ) -> list[Recommendation]:
        query = self._db.query(RecommendationModel)
        if status != "all":
            query = query.filter(
                RecommendationModel.status == status.upper(),
            )
        models = (
            query.order_by(
                RecommendationModel.created_at.desc(),
            )
            .limit(limit)
            .all()
        )
        return [m.to_entity() for m in models]
