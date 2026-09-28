from __future__ import annotations

import csv
import io
from typing import Type

from pydantic import BaseModel

from app.contracts.models import ImportResult
from app.data.repository import Repository
from app.services.data_quality import validate_rows


def parse_csv_bytes(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def import_records(repo: Repository, collection: str, rows: list[dict], model: Type[BaseModel], key: str) -> ImportResult:
    valid, errors, duplicates = validate_rows(rows, model, key)
    imported = 0
    for row in valid:
        repo.upsert(collection, row, key)
        imported += 1
    return ImportResult(collection=collection, imported=imported, rejected=len(errors), duplicate_ids=duplicates, errors=errors)
