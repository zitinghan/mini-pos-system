# Implementation Plan

This machine is a development workstation, not the restaurant deployment host.

1. Foundation: monorepo, versioned SQLite schema, seed tables/menu, first-admin setup, authenticated APIs, Compose health checks.
2. Ordering: persistent sessions and drafts, validated price snapshots, atomic submission and outbox, mobile Chinese interface.
3. Printing: exclusive job claims, mock previews/failures, ESC/POS text/raster, audited manual reprints, uncertain delivery recovery.
4. Checkout: integer-sen billing, draft guard, idempotent full payment, table release and historical transactions.
5. Administration: roles, user provisioning, price editing, printer settings, daily Kuala Lumpur sales.
6. Quality: backend pricing/lifecycle/concurrency tests, frontend tests/build, deployment and safe backups.

Dependencies: Python 3.12+, Node 22+, package registry access; Docker only on the deployment machine or for container verification.

Acceptance: T05 two extra-noodle meals = 2000 sen; second egg meal = 900 sen; only new batch prints; payment of 5000 returns 2100 and releases table. Duplicate requests create one batch/job/payment. Printer failures preserve orders.

## Validation status

Implementation and test results are recorded here as work proceeds. Initial inspection: Python 3.14 and Node 22 available; pip, ensurepip and Docker absent; direct registry DNS unavailable. Existing AGENTS.md preserved.

## Implementation progress

- Foundation source complete: monorepo, explicit Alembic SQL migration, transactional seeds, auth bootstrap, persistent tokens, roles, health and Compose.
- Ordering source complete: mobile tables, persisted owned drafts, minimum/maximum modifier validation, submit idempotency, price snapshots and incremental batches.
- Printing source complete: committed outbox, exclusive worker claims, CJK PNG previews, four mock outcomes, ESC/POS buffer/network adapter, uncertain crash recovery and audited reprints.
- Checkout source complete: authoritative combined bill, expected-total guard, manual QR/other receipt, cash/change, draft discard guard, unique full payment and historical release.
- Administration source complete: user creation, base/modifier price editing, printer controls, daily local-time totals, transactions and audit API.
- Quality artifacts complete: pytest/Vitest/three-width Playwright coverage, CI definition, documentation, SQLite-safe backup/restore.
- Validation partial: seven dependency-free credential/SQLite/backup tests, Python compilation, actual CJK rendering and money utility assertions passed. Dependency installation failed due registry DNS; full suites/build/containers/browser acceptance remain pending. Milestones are **not acceptance-complete** until the checks in `docs/validation.md` run successfully.

Next exact task: on an environment with Python 3.12 and registry access, execute the dependency installation and test/build commands in `docs/validation.md`; fix failures, generate the npm lockfile, then verify Compose and physical hardware on the separate deployment machine.

## Follow-up — 2026-11-04

- Corrected Vitest discovery so Playwright specs are not executed by Vitest.
- Extracted authoritative pricing into a framework-independent service used by the order API; all 12 pricing tests passed (19 standalone tests including prior invariants).
- Added idempotent reprint requests, including protection when the replacement job has already finished; HTTP regression coverage written, pending dependency installation.
- Added direct cashier resume-ordering control on PAYMENT_PENDING tables.
- Current runtime blockers: package DNS unavailable, Docker socket denied, GitHub connector methods return Unknown tool despite appearing in discovery. Source is preserved locally; deployment and remote upload remain unverified.
