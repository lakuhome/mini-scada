import time

from src.core.models import Tag
from src.core.deadband import DeadbandFilter


def make_tag(value: float) -> Tag:
    return Tag(
        id="TEMP_01",
        value=value,
        timestamp=time.time(),
        quality="GOOD",
    )


def test_first_value_is_stored():
    deadband = DeadbandFilter(threshold=0.5)

    assert deadband.should_store(make_tag(75.0)) is True


def test_small_change_is_ignored():
    deadband = DeadbandFilter(threshold=0.5)

    deadband.should_store(make_tag(75.0))

    assert deadband.should_store(make_tag(75.2)) is False


def test_large_change_is_stored():
    deadband = DeadbandFilter(threshold=0.5)

    deadband.should_store(make_tag(75.0))

    assert deadband.should_store(make_tag(75.8)) is True