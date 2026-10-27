import time
import pytest

from src.core.models import Tag
from src.core.bus import InMemoryBus


def test_publish_and_get_tag():
    bus = InMemoryBus()

    tag = Tag(
        id="TEMP_01",
        value=75.4,
        timestamp=time.time(),
        quality="GOOD",
    )

    bus.publish(tag)

    result = bus.get("TEMP_01")

    assert result is not None
    assert result.id == "TEMP_01"
    assert result.value == 75.4
    assert result.quality == "GOOD"


def test_update_tag():
    bus = InMemoryBus()

    first = Tag(
        id="TEMP_01",
        value=75.4,
        timestamp=time.time(),
        quality="GOOD",
    )

    second = Tag(
        id="TEMP_01",
        value=76.2,
        timestamp=time.time(),
        quality="GOOD",
    )

    bus.publish(first)
    bus.publish(second)

    result = bus.get("TEMP_01")

    assert result.value == 76.2

@pytest.mark.asyncio
async def test_subscriber_receives_published_tag():
    bus = InMemoryBus()
    queue = bus.subscribe(replay_current=False)

    bus.publish(
        Tag(
            id="TEMP_01",
            value=75.4,
            quality="GOOD",
        )
    )

    received = await queue.get()


@pytest.mark.asyncio
async def test_subscriber_receives_independent_snapshots():
    bus = InMemoryBus()
    queue = bus.subscribe(replay_current=False)

    tag = Tag(id="TEMP_01", value=75.4, quality="GOOD")
    bus.publish(tag)

    first = await queue.get()

    tag.update_value(80.0)
    bus.publish(tag)

    second = await queue.get()

    assert first.value == 75.4
    assert second.value == 80.0
    assert first.value == 75.4

def test_get_returns_independent_copy():
    bus = InMemoryBus()
    bus.publish(Tag(id="TEMP_01", value=75.4, quality="GOOD"))

    tag = bus.get("TEMP_01")
    tag.value = 100.0

    assert bus.get("TEMP_01").value == 75.4