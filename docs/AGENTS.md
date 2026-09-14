# Documentation scope

Read `decisions/USER_OVERRIDES.md` first. U01–U10 are effective within their recorded scope; P01–P12 are not thereby approved. Preserve unresolved choices as unresolved. U06's domain/transformation modules follow `implementation/MODULE_BOUNDARIES.md` without adding public Record types or splitting atomic commits.

`source/` is immutable historical evidence including baseline_parts. Its bytes/partition are checked by source_map.json. `canonical/` is the current CLI/MinerU/English-name revision with current_map.json and a synchronized full snapshot. Do not mix archived source line references with current line references.

Review F01–F26 and original invariant quotations describe the preserved pre-change source. Keep that evidence unchanged. Apply new wording in current contracts, tasks and canonical. Future canonical edits require a new synchronized snapshot, slice map and tests; never mutate one slice alone.

No GUI work before the CLI gate. PDF parser is MinerU with U05's latest-stable selection policy; exact runtime/backend still requires actual environment verification. U04 records BGE-M3 retrieval defaults. Keep factual upstream descriptions separate from our implementation design.

U07 names the Wisdom synthesis operation K2W and its module k2w. Query/Context inputs and semantics remain unchanged; preserve original invariant quotations and archived names.

U08 applies the scoped R01–R06/R09 repairs in decisions/ARCHITECTURE_FIXES.md. R07/R08 now have explicit approvals: stale decision reconfirmation and exact scoped rejected-FP lookup. Treat history/2026-09-09_pre_architecture_fixes.md as exact preserved pre-fix evidence. Partial acceptance does not accept all P01–P12 details.

U09 applies PostgreSQL 18/pgvector, raw-byte SHA-256 Data IDs, UUIDv7 for other new opaque IDs, tool-managed registration and atomic validated-effect promotion with durable Runtime Records. Read decisions/STORAGE_IDENTITY.md. schema/T02_storage_draft.sql is an unapplied review draft. Preserve earlier history snapshots and unresolved runtime/toolchain choices.

U10 fixes Python as the application language and Docker as the runtime/deployment basis. ENVIRONMENT.md distinguishes actual approved Docker reads from default-sandbox denial. Exact runtime versions/tooling and application/DB execution remain separate from this choice.
