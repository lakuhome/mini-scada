import time

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