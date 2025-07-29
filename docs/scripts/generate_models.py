#!/usr/bin/env python3
"""
generate_models.py

Generate SQLAlchemy 2.0 ORM model classes via reflection,
with support for pgvector's `vector` column type.

Usage:
    # All tables
    python generate_models.py <DATABASE_URL> > models.py

    # Only specific tables
    python generate_models.py <DATABASE_URL> table1 table2 > selected_models.py
"""

import sys
from sqlalchemy import create_engine, MetaData
from sqlalchemy.dialects.postgresql.base import PGDialect
from pgvector.sqlalchemy import Vector
from sqlalchemy.exc import CompileError
from typing import Any


def camel_case(name: str) -> str:
    """snake_case → CamelCase"""
    return "".join(part.capitalize() for part in name.split("_"))


def render_column(col, dialect) -> str:
    """
    Build one line of:
        name: Mapped[PyType] = mapped_column(SQLType(...), kwargs...)
    """
    # 1) Figure out the SQLAlchemy type string
    if isinstance(col.type, Vector):
        # pgvector Vector → keep its dimension
        type_str = f"Vector({col.type.dim})"
    else:
        try:
            # normal types (UUID, TEXT, etc.)
            type_str = col.type.compile(dialect=dialect)
        except CompileError:
            # fallback if something went weird
            type_str = "Any"

    # 2) Collect keyword args
    kw = []
    if col.primary_key:
        kw.append("primary_key=True")
    if not col.nullable:
        kw.append("nullable=False")
    if col.default is not None and getattr(col.default, "arg", None) is not None:
        kw.append(f"default={col.default.arg!r}")
    if col.comment:
        kw.append(f"doc={col.comment!r}")

    # 3) Python type annotation
    try:
        py_type = col.type.python_type.__name__
    except Exception:
        py_type = "Any"

    args = ", ".join([type_str] + kw)
    return f"{col.name}: Mapped[{py_type}] = mapped_column({args})"


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_models.py <DATABASE_URL> [table1 table2 ...]", file=sys.stderr)
        sys.exit(1)

    db_url = sys.argv[1]
    tables_to_emit = sys.argv[2:]  # if empty → all tables

    # 1. Create engine & register pgvector type for reflection
    engine = create_engine(db_url)
    PGDialect.ischema_names["vector"] = Vector

    # 2. Reflect only the requested tables (or everything)
    metadata = MetaData()
    reflect_kwargs: dict[str, Any] = {"bind": engine}
    if tables_to_emit:
        reflect_kwargs["only"] = tables_to_emit
    metadata.reflect(**reflect_kwargs)

    # 3. Emit header
    print("from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column")
    print("from sqlalchemy import *")
    print("from pgvector.sqlalchemy import Vector")
    print("from datetime import datetime, timezone")
    print()

    # 4. Base class
    print("class Base(DeclarativeBase):")
    print("    metadata = metadata")
    print()

    # 5. One class per table
    for table_name, table in metadata.tables.items():
        cls_name = camel_case(table_name)
        print(f"class {cls_name}(Base):")
        print(f"    __tablename__ = {table_name!r}")
        for col in table.columns:
            print("    " + render_column(col, engine.dialect))
        print()  # blank line between classes


if __name__ == "__main__":
    main()
