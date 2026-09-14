# Plans for multi-step work

Use a task-local `progress/Txx_execplan.md` only when work needs a durable multi-step handoff. A small documentation or reversible fix can be described in the commit and completion report.

Keep the plan focused: intended outcome, relevant code/contract, concrete steps, important decisions/approval boundaries, and pending verification. Update it as work changes; do not copy all historical releases or entire tool outputs. Preserve actual failures and unresolved issues without claiming later work complete.

At completion update `progress/STATUS.md` in place if delivery state changed. Link one detailed task report with executed checks and limitations. README, INDEX and AGENTS are stable navigation/rules, not parallel status logs. Use Git for code/document diffs and recovery; use exact artifact/DB provenance for source data.
