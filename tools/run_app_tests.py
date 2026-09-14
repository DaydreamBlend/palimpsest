"""Run real application checks inside an explicitly selected test project."""

import os
from pathlib import Path
import sys
import unittest

if __name__ == "__main__":
    secret_path = os.environ.get("PALIMPSEST_DATABASE_DSN_FILE")
    if not secret_path:
        raise SystemExit("A dedicated Compose test database is required")
    os.environ["PALIMPSEST_TEST_DSN"] = Path(secret_path).read_text().strip()
    suite = unittest.defaultTestLoader.discover("tests/app", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
