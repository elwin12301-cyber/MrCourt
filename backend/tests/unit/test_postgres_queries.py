"""Queries that only run on PostgreSQL are at least built and compiled here (the tests use SQLite)."""
from sqlalchemy.dialects import postgresql

from mrcourt.services.retrieval import meaning_query


def test_the_meaning_query_compiles_for_postgresql():
    sql = str(meaning_query(None, [0.1] * 1024, 20).compile(dialect=postgresql.dialect()))
    assert "<=>" in sql and "ORDER BY d" in sql and "LIMIT" in sql
