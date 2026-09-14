# Documentation scope

- `../progress/STATUS.md` is current delivery state; use `INDEX.md` for the task's relevant current interface/decision. Historical task numbers and dates do not override current user choices.
- Preserve `source/`, historical snapshots and their exact hashes. `canonical/` is a synchronized base specification: edit its full snapshot, slices and map together only when the task changes that specification. Later approved interface/decision scopes may supersede older clauses.
- Keep proposals unresolved unless explicitly approved. Consult `decisions/USER_OVERRIDES.md` and `DECISION_REGISTER.md` only for the affected approval, not as a mandatory full-history read. Electron has already been explicitly started; old GUI-last text is historical.
- Store current state once, detailed outcomes in task reports and old entry prose in Git history. Do not prepend a new release narrative to README/INDEX/AGENTS on every task.
- For documentation changes run `python tools/validate_bundle.py` and relevant link checks. They validate documents, not app behavior or DB transactions. Report pre-existing broken evidence links separately; do not fabricate missing artifacts.
