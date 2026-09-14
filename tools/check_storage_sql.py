"""Run the preserved rollback-only SQL fixture in the dedicated test DB."""

import os
from pathlib import Path
import psycopg

if __name__ == "__main__":
    dsn = Path(os.environ["PALIMPSEST_ADMIN_DSN_FILE"]).read_text().strip()
    with psycopg.connect(dsn,autocommit=True) as connection:
        connection.execute(Path("tests/sql/T02_storage_checks.sql").read_text(),prepare=False)
    print("Storage SQL constraints: PASS (fixture rolled back)")
