"""Tests for InMemoryDebateBus pub/sub."""

from __future__ import annotations

import asyncio

import pytest

from daily_scheduler.infrastructure.adapters.debate.in_memory_debate_bus import (
    DebateEvent,
    InMemoryDebateBus,
)


@pytest.mark.asyncio
async def test_subscribe_receives_published_events() -> None:
    bus = InMemoryDebateBus()
    received: list[DebateEvent] = []

    async def reader() -> None:
        async for event in bus.subscribe("d1"):
            received.append(event)
            if event.kind == "debate_done":
                break

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)  # let reader subscribe

    bus.publish("d1", DebateEvent(kind="analyst_start", payload={}))
    bus.publish("d1", DebateEvent(kind="debate_done", payload={}))

    await asyncio.wait_for(task, timeout=2)
    assert len(received) == 2
    assert received[0].kind == "analyst_start"
    assert received[1].kind == "debate_done"


@pytest.mark.asyncio
async def test_subscribe_ignores_other_debate_ids() -> None:
    bus = InMemoryDebateBus()
    received: list[DebateEvent] = []

    async def reader() -> None:
        async for event in bus.subscribe("d1"):
            received.append(event)
            if event.kind == "debate_done":
                break

    task = asyncio.create_task(reader())
    await asyncio.sleep(0)
    bus.publish("d2", DebateEvent(kind="analyst_start", payload={}))
    bus.publish("d1", DebateEvent(kind="debate_done", payload={}))
    await asyncio.wait_for(task, timeout=2)
    assert len(received) == 1
    assert received[0].kind == "debate_done"


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive() -> None:
    bus = InMemoryDebateBus()
    r1: list[DebateEvent] = []
    r2: list[DebateEvent] = []

    async def reader(target: list[DebateEvent]) -> None:
        async for event in bus.subscribe("d1"):
            target.append(event)
            if event.kind == "debate_done":
                break

    t1 = asyncio.create_task(reader(r1))
    t2 = asyncio.create_task(reader(r2))
    await asyncio.sleep(0)
    bus.publish("d1", DebateEvent(kind="round_start", payload={"idx": 0}))
    bus.publish("d1", DebateEvent(kind="debate_done", payload={}))
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=2)
    assert len(r1) == 2
    assert len(r2) == 2
