"""Agents API routes — role catalog + binding overrides."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from daily_scheduler.database import get_db
from daily_scheduler.domain.entities.agent import (
    BackendBinding,
    Provider,
    Role,
    roles_for_pipeline,
)
from daily_scheduler.infrastructure.adapters.council.role_registry import (
    default_binding_for,
    tools_for_role,
)
from daily_scheduler.infrastructure.adapters.persistence.agent_binding_repository import (
    SQLAlchemyAgentBindingRepository,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])

_PIPELINES: tuple[str, ...] = ("daily", "news", "global-news", "weekly")


class BindingIn(BaseModel):
    """Incoming binding override payload."""

    provider: str
    model: str
    system_prompt_override: str | None = None
    timeout_s: int = 600


def _serialize_binding(binding: BackendBinding) -> dict[str, Any]:
    return {
        "provider": binding.provider.value,
        "model": binding.model,
        "system_prompt_override": binding.system_prompt_override,
        "timeout_s": binding.timeout_s,
    }


def _pipelines_for(role: Role) -> list[str]:
    return [p for p in _PIPELINES if role in roles_for_pipeline(p)]


@router.get("")
def list_agents(db: Session = Depends(get_db)) -> dict[str, Any]:
    """List every Role with its current binding, tools, and pipelines."""
    repo = SQLAlchemyAgentBindingRepository(db)
    items: list[dict[str, Any]] = []
    for role in Role:
        binding = repo.get(role) or default_binding_for(role)
        items.append(
            {
                "role": role.value,
                "binding": _serialize_binding(binding),
                "tools": tools_for_role(role),
                "pipelines": _pipelines_for(role),
            }
        )
    return {"items": items}


@router.get("/{role}")
def get_agent(role: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return a single role's binding + tools or 404 when unknown."""
    try:
        role_enum = Role(role)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="role not found") from exc
    repo = SQLAlchemyAgentBindingRepository(db)
    binding = repo.get(role_enum) or default_binding_for(role_enum)
    return {
        "role": role_enum.value,
        "binding": _serialize_binding(binding),
        "tools": tools_for_role(role_enum),
        "pipelines": _pipelines_for(role_enum),
    }


@router.put("/{role}/binding")
def put_binding(
    role: str,
    body: BindingIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Persist a binding override for ``role``."""
    try:
        role_enum = Role(role)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="role not found") from exc
    try:
        provider = Provider(body.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo = SQLAlchemyAgentBindingRepository(db)
    repo.upsert(
        role_enum,
        BackendBinding(
            provider=provider,
            model=body.model,
            system_prompt_override=body.system_prompt_override,
            timeout_s=body.timeout_s,
        ),
    )
    return {"ok": True}
