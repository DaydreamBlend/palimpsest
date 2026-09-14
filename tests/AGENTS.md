# Test scope

- Use the current contracts selected through `docs/INDEX.md`; old acceptance specifications and proposed P decisions do not establish implementation or approval. Preserve immutable source/invariant mappings.
- Verify the boundary affected by the change: exact refs, source identity, materiality, delayed applicability, stale inputs, retry/crash/atomicity, and real confirmation where relevant. Do not duplicate suites or weaken assertions to reach a milestone.
- Pure/mock tests are not PostgreSQL transaction tests or model quality evidence. Use isolated, explicitly selected DB/artifact roots for integration. Never migrate user DBs in tests, rerun user-source D2I, or call a provider without the applicable authorization.
- Report actual pass/failure/skip counts. Execute an actual pinned parser separately from synthetic fixtures. Documentation-only changes do not require the app/DB/model suites.
