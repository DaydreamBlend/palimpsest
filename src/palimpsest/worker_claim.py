"""Keep one host worker's execution claim for the lifetime of its stdin pipe.

This session lock serializes cooperating workers, not canonical publication.
Closing the connection releases it even if explicit unlock cannot run.
"""

import os
import sys
from threading import Event, Thread

from .canonical_store import connection
from .data import request_id
from .errors import PalimpsestError


CLAIM_SEED = 7429160301


def hold_claim(dsn, execution_id, on_acquired):
    """Acknowledge only an acquired claim, then hold it until stdin EOF.

    The caller keeps the pipe open and must stop inference if its holder exits.
    No database transaction stays open while the host performs model calls.
    """
    execution_id = request_id(execution_id)
    with connection(dsn) as conn:
        exists = conn.execute(
            "SELECT 1 FROM compiler_runtime.operation_executions WHERE execution_id=%s",
            (execution_id,),
        ).fetchone()
        if exists is None:
            raise PalimpsestError("job_not_found", "D2I 실행을 찾을 수 없습니다.", 2)
        acquired = conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,%s)) AS acquired",
            (execution_id, CLAIM_SEED),
        ).fetchone()["acquired"]
        if not acquired:
            raise PalimpsestError("job_busy", "다른 worker가 이 D2I 실행을 처리하고 있습니다.", 6)
        try:
            on_acquired()
            finished = Event()
            failures = []
            source_fd = sys.stdin.fileno()

            def read_input():
                try:
                    # A daemon must not hold BufferedReader's lock at interpreter
                    # shutdown when a lost DB session terminates the main thread.
                    while os.read(source_fd, 65536):
                        pass
                except BaseException as exc:
                    failures.append(exc)
                finally:
                    finished.set()

            Thread(target=read_input, name="palim-worker-stdin", daemon=True).start()
            while not finished.wait(5):
                conn.execute("SELECT 1")
            if failures:
                raise failures[0]
        finally:
            if not conn.closed:
                conn.execute("SELECT pg_advisory_unlock(hashtextextended(%s,%s))",
                             (execution_id, CLAIM_SEED))
