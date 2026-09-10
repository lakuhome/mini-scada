import time

from src.core.models import Tag
from src.storage.database import Database


def test_database_saves_and_reads_tag(tmp_path):
    db = Database(str(tmp_path / "test.db"))

    tag = Tag(
        id="TEMP_01",
        value=75.5,
        timestamp=time.time(),
        quality="GOOD",
    )

    db.save_tag(tag)

    history = db.get_history("TEMP_01")

    assert len(history) == 1
    assert history[0].id == "TEMP_01"
    assert history[0].value == 75.5
    assert history[0].quality == "GOOD"