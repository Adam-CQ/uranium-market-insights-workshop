from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.db.schema import metrics, observations, runs
from app.ingestion.cameco_prices import SourceFormatError
from app.ingestion.price_repository import import_prices

FIXTURE = Path(__file__).parent / "fixtures" / "cameco_prices_synthetic.html"
TIME = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


@pytest.fixture
def importer(database, tmp_path):
    # Keep repository commits inside the test's outer rollback transaction.
    from contextlib import contextmanager

    @contextmanager
    def begin():
        with database.begin_nested():
            yield database

    engine = SimpleNamespace(begin=begin)
    def run(body=FIXTURE.read_bytes(), when=TIME):
        return import_prices(engine, body, retrieved_at=when, raw_dir=tmp_path, synthetic=True)
    return run


def test_file_import_is_idempotent_and_keeps_artifact(database, importer, tmp_path):
    body = FIXTURE.read_bytes()
    first = importer(body)
    second = importer(body)
    assert first["added"] == 8
    assert second["added"] == 0
    assert second["revised"] == 0
    assert second["unchanged"] == 8
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 8
    assert (tmp_path / f"{sha256(body).hexdigest()}.html").read_bytes() == body
    assert database.scalar(sa.select(sa.func.count()).select_from(runs).where(runs.c.status == "succeeded")) == 2
    assert set(database.scalars(sa.select(observations.c.data_status))) == {"mock"}
    run = database.execute(sa.select(runs).where(runs.c.id == first["run_id"])).mappings().one()
    assert run["source_publication_date"] is None
    assert run["retrieved_at"] == TIME
    assert run["artifact_sha256"] == first["checksum"]
    assert list(database.scalars(sa.select(metrics.c.unit))) == ["USD/lb U3O8", "USD/lb U3O8"]


def test_revision_preserves_old_value_and_page_chrome_changes_do_not_duplicate(database, importer):
    importer()
    # A page edit outside the table produces a different artifact, but no new facts.
    result = importer(FIXTURE.read_bytes().replace(b"<title>", b"<title>New "))
    assert result["added"] == result["revised"] == 0
    revised = importer(FIXTURE.read_bytes().replace(b"76.00", b"77.00"), TIME + timedelta(days=1))
    assert revised["revised"] == 1
    assert revised["unchanged"] == 7
    revised_row = database.execute(sa.select(observations).where(observations.c.supersedes_observation_id.is_not(None))).mappings().one()
    previous = database.execute(sa.select(observations).where(observations.c.id == revised_row["supersedes_observation_id"])).mappings().one()
    assert previous["normalized_value"] == 76
    assert revised_row["normalized_value"] == 77
    # Replaying an older already-successful artifact must not undo a later revision.
    assert importer()["revised"] == 0
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 9


def test_parse_failure_logs_run_and_writes_no_partial_observations(database, importer):
    with pytest.raises(SourceFormatError):
        importer(b"<html>Unexpected source structure</html>")
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 0
    assert database.scalar(sa.select(runs.c.status)) == "failed"


def test_old_changed_snapshot_and_truncated_history_fail_atomically(database, importer):
    importer()
    with pytest.raises(ValueError, match="not newer"):
        importer(FIXTURE.read_bytes().replace(b"76.00", b"75.00"), TIME - timedelta(days=1))
    body = FIXTURE.read_text()
    truncated = "\n".join(line for line in body.splitlines() if "2004/04/01" not in line).encode()
    with pytest.raises(ValueError, match="disappeared"):
        importer(truncated, TIME + timedelta(days=1))
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 8
    assert database.scalar(sa.select(sa.func.count()).select_from(runs).where(runs.c.status == "failed")) == 2


def test_permission_check_happens_before_database_or_file_writes(tmp_path):
    with pytest.raises(ValueError, match="permission"):
        import_prices(None, FIXTURE.read_bytes(), retrieved_at=TIME, raw_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_replay_of_older_successful_file_after_new_month_is_a_noop(database, importer):
    importer()
    extended = FIXTURE.read_bytes().replace(
        b"</tbody>", b"<tr><td>2025/07/31</td><td>78.00</td><td>84.00</td></tr></tbody>"
    )
    assert importer(extended, TIME + timedelta(days=1))["added"] == 2
    assert importer()["unchanged"] == 8
    assert database.scalar(sa.select(sa.func.count()).select_from(observations)) == 10
