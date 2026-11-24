"""SQLite database engine, session factory, and initialization helpers."""

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def _configure_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enable WAL mode, foreign keys, and busy timeout for concurrent submissions."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


def create_db_engine(database_url: str | None = None):
    """Build SQLAlchemy engine configured for SQLite concurrency."""
    url = database_url or settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    db_engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        event.listen(db_engine, "connect", _configure_sqlite_pragma)
    return db_engine


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Ensure storage directories exist, create tables, and apply lightweight SQLite migrations."""
    settings.ensure_directories()
    # Import models here so metadata registers every table before create_all.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Safely add new session report columns when upgrading an existing smartclass.db.
    if str(engine.url).startswith("sqlite"):
        with engine.begin() as conn:
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sessions)").fetchall()}
            if "total_detected" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE sessions ADD COLUMN total_detected INTEGER NOT NULL DEFAULT 0"
                )
            if "students_left_early" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE sessions ADD COLUMN students_left_early INTEGER NOT NULL DEFAULT 0"
                )

            # Course-scoped forum threads (added for course-based forum categorization).
            forum_cols = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(forum_posts)").fetchall()
            }
            if "course_id" not in forum_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE forum_posts ADD COLUMN course_id VARCHAR(36) REFERENCES courses(id)"
                )
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_forum_posts_course_id ON forum_posts (course_id)"
                )
            if "title" not in forum_cols:
                conn.exec_driver_sql("ALTER TABLE forum_posts ADD COLUMN title VARCHAR(200)")
