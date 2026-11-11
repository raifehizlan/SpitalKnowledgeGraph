"""Copy the loaded PostgreSQL pilot into data/pilot.sqlite.

The screen reads that file. Run this again after the PostgreSQL data changes.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from swiss_hospital_intelligence.database.schema import Base

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "pilot.sqlite"
POSTGRES = "postgresql+psycopg://shi:shi@localhost:5432/shi"
BATCH = 200


def main() -> int:
    if TARGET.exists():
        TARGET.unlink()
    source = create_engine(POSTGRES)
    target = create_engine(f"sqlite:///{TARGET.resolve().as_posix()}")
    Base.metadata.create_all(target)
    with Session(source) as incoming, target.begin() as outgoing:
        for table in Base.metadata.sorted_tables:
            rows = incoming.execute(select(table)).mappings().all()
            for start in range(0, len(rows), BATCH):
                batch = [dict(row) for row in rows[start : start + BATCH]]
                if batch:
                    outgoing.execute(table.insert(), batch)
            print(f"{table.name}: {len(rows)}")
    print(TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
