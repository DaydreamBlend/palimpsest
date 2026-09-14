# Test scope

`specs/acceptance_catalog.json` and `specs/ACCEPTANCE.md` are unimplemented Given/When/Then specifications. `spec_only` must not be converted to passed without a real implementation test and execution result.

For proposed contracts, confirm required P decisions before enforcing them as production expectations. Preserve the original invariant mapping; update it with new test paths as code is implemented.

Test no-material stopping, exact effective-edge refs, delayed applicability, stale read sets, crashes/redelivery, and confirmation retries. Mock DB tests do not establish PostgreSQL transaction behavior. Mock LLM tests do not establish semantic correctness. Never replace assertions with unconditional pass to meet a milestone.


## Current user decisions

U01–U03 already select CLI-first/GUI-last, MinerU PDF parsing and the new component names. Verify their linked AT scenarios without treating unapproved P details as accepted. Test CLI with no display/browser and non-TTY stdin; keep stdout JSON clean. Test an actual pinned MinerU separately from synthetic parser fixtures. No silent parser fallback, no fabricated authority, no destructive legacy rename.

U08 applies only the recorded resolved architecture clauses in docs/decisions/ARCHITECTURE_FIXES.md. AT106/AT107 depend on separate R07/R08 choices; do not pick an option from its recommendation without actual user evidence. Original invariant quotations are historical; compare current behavior to the applied U08 scope without rewriting archived text.

U09 follows docs/decisions/STORAGE_IDENTITY.md. Distinguish exact-byte duplicate rejection, same-request success replay and explicit acquisition provenance. UUIDv7 is not a commit ordering token. docs/schema/T02_storage_checks.sql is an unexecuted PostgreSQL fixture until an actual run is recorded. Document checks are not DB, filesystem, race, or application tests.
