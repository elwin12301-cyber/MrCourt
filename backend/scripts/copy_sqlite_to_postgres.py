"""One-time copy of a development SQLite database into PostgreSQL (same schema, run migrations first).

    alembic upgrade head            (with DATABASE_URL pointing at PostgreSQL)
    python scripts/copy_sqlite_to_postgres.py --source sqlite:///./dev.db ^
        --target postgresql+psycopg://mrcourt:mrcourt@localhost:5432/mrcourt

Rows are read and written through the app's own table definitions, so ids, JSON and embeddings convert to the
PostgreSQL types. Foreign-key checks are paused during the copy (the target user must be allowed to do that,
as the Docker database owner is). Refuses to write into a database that already has users, unless --replace.
"""

import argparse

from sqlalchemy import create_engine, func, inspect, select, text

import mrcourt.models  # noqa: F401 - registers every table
from mrcourt.db.base import Base

BATCH = 500


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--replace", action="store_true", help="empty the target tables first")
    args = parser.parse_args()

    source = create_engine(args.source)
    target = create_engine(args.target)
    tables = Base.metadata.sorted_tables
    with target.begin() as out:
        users = Base.metadata.tables["users"]
        if out.scalar(select(func.count()).select_from(users)) and not args.replace:
            raise SystemExit("The target already has users. Use --replace to overwrite it.")
        out.execute(text("SET session_replication_role = replica"))  # pause foreign-key checks
        if args.replace:
            out.execute(text("TRUNCATE " + ", ".join(f'"{t.name}"' for t in tables) + " CASCADE"))
        with source.connect() as src:
            present = {name: {c["name"] for c in inspect(src).get_columns(name)} for name in inspect(src).get_table_names()}
            for table in tables:
                if table.name not in present:
                    print(f"{table.name:22} (not in the source)")
                    continue
                # search_vector is rebuilt by PostgreSQL search; columns added by newer migrations stay empty.
                columns = [c for c in table.columns if c.name != "search_vector" and c.name in present[table.name]]
                rows = src.execute(select(*columns)).mappings()
                count, batch = 0, []
                for row in rows:
                    batch.append(dict(row))
                    if len(batch) >= BATCH:
                        out.execute(table.insert(), batch)
                        count, batch = count + len(batch), []
                if batch:
                    out.execute(table.insert(), batch)
                    count += len(batch)
                print(f"{table.name:22} {count}")
        out.execute(text("SET session_replication_role = DEFAULT"))
    print("Done.")


if __name__ == "__main__":
    main()
