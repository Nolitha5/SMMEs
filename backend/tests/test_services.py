import pytest

from app.services.storage import archive_import
from app.worker import run_daily_procurement


def test_import_archive_generates_checksum_without_cloud_storage():
    meta = archive_import(b"a,b\n1,2\n", "sample.csv", "tester")
    assert meta["sha256"]
    assert meta["bytes"] == 8
    assert meta["storage_uri"] is None


@pytest.mark.asyncio
async def test_daily_worker_refreshes_active_supplier_scores(repo):
    result = await run_daily_procurement()
    assert result["suppliers_refreshed"] == 3
    assert len(result["results"]) == 3
