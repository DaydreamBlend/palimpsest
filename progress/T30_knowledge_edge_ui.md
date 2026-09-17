# T30 — K Node / K Edge desktop view

Status: completed on 2026-09-17.

The read-only Knowledge catalog now returns separately typed `nodes` and `edges`.
Node origin badges use the preserved operation (`I2K`, `K2K`, or `D2K`). Edge
entries remain canonical K Edge records and are labelled `N2E`; no Edge is
converted into a K Node and no storage migration was performed.

The Electron Knowledge screen provides `K Node` and `K Edge` selectors. The Node
list also filters by `I2K` or `K2K` origin, so inferred Nodes remain directly
findable without treating an N2E Edge as a Node. Edge details show the exact
semantic Edge Revision, predicate, applicability, From/To Node Revisions,
rationale, and qualifiers. Realm/store scoping still happens in the read service
before data reaches the renderer.

Actual pharmacy-store verification returned 713 Nodes (712 I2K, one K2K) and
262 N2E Edges with predicates `composes`, `contradicts`, `qualifies`, and
`supports`. A separate hidden packaged Electron instance rendered both lists and
an Edge detail with zero renderer errors. The launch package is
`output/t30-knowledge-edge-ui/release-k2k/app.asar`.
