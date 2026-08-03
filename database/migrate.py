"""Applies numbered migration files in database/migrations/ in order.

Usage (from repo root): python -m database.migrate

Each migration is a .sql file named "<number>_<description>.sql". A
schema_migrations table tracks which versions have already been applied, so
re-running this script only applies new migrations. Each migration runs in
its own transaction; a failure stops the run without recording that version.
"""

import pathlib

import psycopg

MIGRATIONS_DIR = pathlib.Path(__file__).parent / "migrations"


def get_connection():
    return psycopg.connect(
        dbname="research_lab_finder",
        user="siddanthkarthik",
        autocommit=False,
    )


def ensure_migrations_table(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    connection.commit()


def get_applied_versions(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cursor.fetchall()}


def get_migration_files():
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_migration(connection, path):
    version = path.stem
    sql = path.read_text()
    with connection.cursor() as cursor:
        cursor.execute(sql)
        cursor.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
        )
    connection.commit()
    print(f"applied {version}")


def run():
    connection = get_connection()
    try:
        ensure_migrations_table(connection)
        applied = get_applied_versions(connection)
        pending = [p for p in get_migration_files() if p.stem not in applied]

        if not pending:
            print("no pending migrations")
            return

        for path in pending:
            try:
                apply_migration(connection, path)
            except Exception:
                connection.rollback()
                print(f"failed on {path.stem}, stopping")
                raise
    finally:
        connection.close()


if __name__ == "__main__":
    run()
