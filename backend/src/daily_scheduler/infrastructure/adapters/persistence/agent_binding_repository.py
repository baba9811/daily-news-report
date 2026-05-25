"""SQLAlchemy adapter for AgentBindingRepositoryPort."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy.orm import Session

from daily_scheduler.domain.entities.agent import BackendBinding, Provider, Role
from daily_scheduler.infrastructure.adapters.persistence.models import (
    AgentBindingModel,
)


class SQLAlchemyAgentBindingRepository:
    """SQLAlchemy-backed implementation of AgentBindingRepositoryPort."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, role: Role) -> BackendBinding | None:
        row = self._s.get(AgentBindingModel, role.value)
        if row is None:
            return None
        return self._row_to_binding(row)

    def upsert(self, role: Role, binding: BackendBinding) -> None:
        row = self._s.get(AgentBindingModel, role.value)
        now = datetime.now()
        if row is None:
            row = AgentBindingModel(
                role=role.value,
                provider=binding.provider.value,
                model=binding.model,
                system_prompt_override=binding.system_prompt_override,
                timeout_s=binding.timeout_s,
                updated_at=now,
            )
            self._s.add(row)
        else:
            row.provider = binding.provider.value
            row.model = binding.model
            row.system_prompt_override = binding.system_prompt_override
            row.timeout_s = binding.timeout_s
            row.updated_at = now
        self._s.commit()

    def delete(self, role: Role) -> None:
        row = self._s.get(AgentBindingModel, role.value)
        if row is not None:
            self._s.delete(row)
            self._s.commit()

    def list_all(self) -> Iterator[tuple[Role, BackendBinding]]:
        for row in self._s.query(AgentBindingModel).all():
            yield Role(row.role), self._row_to_binding(row)

    @staticmethod
    def _row_to_binding(row: AgentBindingModel) -> BackendBinding:
        return BackendBinding(
            provider=Provider(row.provider),
            model=row.model,
            system_prompt_override=row.system_prompt_override,
            timeout_s=row.timeout_s,
        )
