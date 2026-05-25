"""Render agent system prompts from Jinja2 templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from daily_scheduler.domain.entities.agent import Role

_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "templates" / "prompts" / "agents"
)

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)


def render_agent_prompt(role: Role, context: dict[str, Any]) -> str:
    """Render the Jinja2 template for ``role`` against ``context``.

    The returned string is the full system prompt for the agent. Templates
    are stored under ``templates/prompts/agents/{role}.j2``.
    """
    template_name = f"{role.value}.j2"
    tpl = _env.get_template(template_name)
    return tpl.render(**context)
