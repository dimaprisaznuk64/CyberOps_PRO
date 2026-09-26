from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.asset import Asset
from app.models.scan import SCAN_DONE, SCAN_FAILED, SCAN_PENDING, SCAN_RUNNING, Scan
from app.models.user import User
from app.services.auth import hash_password
from app.services.scans import STALE_ERROR, fail_stale_scans

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


async def _seed(session_factory) -> dict[str, Scan]:
    async with session_factory() as session:
        user = User(username="analyst", password_hash=hash_password("x"), role="analyst")
        session.add(user)
        await session.flush()
        asset = Asset(name="web", host="127.0.0.1", owner_id=user.id)
        session.add(asset)
        await session.flush()

        old_pending = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_PENDING,
            created_at=NOW - timedelta(hours=2),
        )
        old_running = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_RUNNING,
            created_at=NOW - timedelta(hours=2),
            started_at=NOW - timedelta(hours=1),
        )
        fresh_pending = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_PENDING,
            created_at=NOW - timedelta(seconds=10),
        )
        fresh_running = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_RUNNING,
            created_at=NOW - timedelta(minutes=2),
            started_at=NOW - timedelta(minutes=2),
        )
        done = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_DONE,
            created_at=NOW - timedelta(hours=5),
            finished_at=NOW - timedelta(hours=5),
        )
        failed = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_FAILED,
            created_at=NOW - timedelta(hours=9),
            finished_at=NOW - timedelta(hours=9),
        )
        session.add_all([old_pending, old_running, fresh_pending, fresh_running, done, failed])
        await session.commit()
        return {
            "old_pending": old_pending,
            "old_running": old_running,
            "fresh_pending": fresh_pending,
            "fresh_running": fresh_running,
            "done": done,
            "failed": failed,
        }


async def test_reaps_only_stale_pending_and_running(session_factory):
    seeded = await _seed(session_factory)

    async with session_factory() as session:
        reaped = await fail_stale_scans(session, stale_after_seconds=900, now=NOW)

    assert sorted(reaped) == sorted(
        [seeded["old_pending"].id, seeded["old_running"].id]
    )

    async with session_factory() as session:
        for key, expected in (
            ("old_pending", SCAN_FAILED),
            ("old_running", SCAN_FAILED),
            ("fresh_pending", SCAN_PENDING),
            ("fresh_running", SCAN_RUNNING),
            ("done", SCAN_DONE),
            ("failed", SCAN_FAILED),
        ):
            scan = await session.get(Scan, seeded[key].id)
            assert scan.status == expected, key


async def test_reaped_scan_gets_error_and_finished_at(session_factory):
    seeded = await _seed(session_factory)

    async with session_factory() as session:
        await fail_stale_scans(session, stale_after_seconds=900, now=NOW)

    async with session_factory() as session:
        scan = await session.get(Scan, seeded["old_running"].id)
        assert scan.error == STALE_ERROR
        assert scan.finished_at is not None
        finished = scan.finished_at
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=UTC)
        assert finished == NOW


async def test_nothing_to_reap_returns_empty(session_factory):
    async with session_factory() as session:
        user = User(username="a2", password_hash=hash_password("x"), role="analyst")
        session.add(user)
        await session.flush()
        asset = Asset(name="web2", host="127.0.0.2", owner_id=user.id)
        session.add(asset)
        await session.flush()
        session.add(
            Scan(
                asset_id=asset.id,
                created_by=user.id,
                status=SCAN_PENDING,
                created_at=NOW - timedelta(seconds=5),
            )
        )
        await session.commit()

    async with session_factory() as session:
        assert await fail_stale_scans(session, stale_after_seconds=900, now=NOW) == []


async def test_naive_timestamps_are_treated_as_utc(session_factory):
    """БД може віддати datetime без tzinfo — інакше порівняння впаде."""
    async with session_factory() as session:
        user = User(username="a3", password_hash=hash_password("x"), role="analyst")
        session.add(user)
        await session.flush()
        asset = Asset(name="web3", host="127.0.0.3", owner_id=user.id)
        session.add(asset)
        await session.flush()
        scan = Scan(
            asset_id=asset.id,
            created_by=user.id,
            status=SCAN_PENDING,
            created_at=datetime(2026, 1, 1, 9, 0, 0),  # naive, 3 години тому
        )
        session.add(scan)
        await session.commit()
        scan_id = scan.id

    async with session_factory() as session:
        reaped = await fail_stale_scans(session, stale_after_seconds=900, now=NOW)

    assert reaped == [scan_id]
