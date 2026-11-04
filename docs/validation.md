# Validation Record

## Latest check — 2026-11-04

Docker 29.1.3, Compose 2.40.3 and pip 25.1.1 are now installed. A Python 3.14 virtual environment can be created successfully. Application dependency installation still fails (the managed session cannot resolve package registries), and the Docker daemon socket returns permission denied. No backend framework or pytest is installed locally. GitHub connector tools now appear in discovery, but actual repository/profile/fetch calls return `Unknown tool`; neither Git transport nor the connector has successfully uploaded code.

Added an independent pricing service used by the real order controller. Its 12 unittest cases pass: all six menu prices, the RM29 bill/RM21 change, selection validation, optional/multiple selections, integer-only money, quantity limits and immutable quote values. Together with the seven credential/SQLite/backup checks, 19 standalone tests pass. This is not full HTTP or browser acceptance.

Fixed Vitest discovery to include only source unit tests, excluding Playwright browser specs. Added idempotent manual-reprint requests and a regression test for replay after a completed reprint, plus a direct cashier “resume ordering” action. The new HTTP regression test remains pending framework dependencies.

## Original environment inspection — 2026-11-03

Inspected on 2026-11-03: Python 3.14.4, Node 22.22.2, npm 10.9.7. Docker is absent. Python has no pip, ensurepip or pytest. Creating `.venv` failed because ensurepip is unavailable; fetching pip failed DNS resolution. `npm install` failed with EAI_AGAIN for registry.npmjs.org. This workstation is not the deployment computer. The incomplete virtual environment was removed. No machine-wide packages, network interfaces or physical printer settings were changed.

## Actually executed

| Check | Outcome |
| --- | --- |
| `python3 scripts/check_invariants.py` | 7 tests passed: salted PIN hashing/verification, opaque token fingerprints, frozen SQLite schema/FKs, active-session unique constraint/reopen, six concurrent opens, submission/payment uniqueness, WAL-safe backup and stopped restore |
| `python3 -m compileall -q backend scripts` | Passed Python syntax compilation |
| Direct Pillow ticket rendering using installed CJK font | Passed: 384-dot monochrome PNG, Chinese modifiers, large T05, quantity/portion total, no prices, REPRINT header |
| Node native TypeScript stripping plus money utility assertions | Passed: decimal-to-sen parsing, invalid fractional sen/negative rejection, RM29 bill and RM21 change |
| Node native parser, eight non-JSX TypeScript source/test files | Passed syntax transformation; does not check types or TSX |
| `sh -n scripts/backup.sh scripts/restore.sh` | Passed shell syntax check |
| `node --check frontend/public/sw.js` | Passed service-worker JavaScript syntax check |
| `python3 -m pytest` | Blocked: pytest and application dependencies not installed |
| `npm run build` | Blocked: tsc not installed |
| `npm test` | Blocked: vitest not installed |
| JSON, Compose/CI YAML and shared-volume configuration | Parsed and inspected successfully; not a Docker runtime test |
| Docker/Compose and real printer | Not run: Docker/hardware unavailable |

The original environment limitations above are superseded by the latest check where noted. These checks do not establish that the complete API/UI or containers run correctly. The pytest, Vitest and Playwright files are implemented test coverage, not reported passing results.

## Implemented automated coverage, pending execution

Backend: six menu prices; complete A/B/C scenario; additional-ticket isolation; immutable historical prices; concurrent opens/submissions/payments; idempotency key conflicts; invalid/duplicate modifiers; draft bill exclusion; insufficient cash; explicit draft discard; role/session/logout/lockout; printer failure/timeout/unknown/reprint; exclusive worker claim and crash recovery; transaction rollback when outbox creation fails; Kuala Lumpur date boundaries; fresh migration and non-destructive reseed.

Frontend: exact sen formatting/parsing, modifier replacement, extra-noodle quantity/total, disabled save button. Playwright runs the main ordering/additional-order/preview/checkout/history scenario at widths 360, 390 and 412 using a temporary isolated database and mock worker. It saves screenshots/traces on failure. CI files run these suites on a dependency-enabled host; they have not been executed from this workspace.

## Exact next steps on a dependency-enabled development machine

Use Python 3.12, not this workstation's unprepared 3.14 environment:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
(cd backend && ../.venv/bin/python -m pytest)
(cd frontend && npm install)
(cd frontend && npm run format && npm run lint && npm test && npm run build)
(cd frontend && npx playwright install chromium && npm run test:e2e)
(cd backend && ../.venv/bin/ruff check . && ../.venv/bin/ruff format .)
```

Resolve failures, rerun affected suites and commit the generated `frontend/package-lock.json`. Switch Docker/CI installs to `npm ci` after this verified lockfile exists. Pin/audit a complete Python dependency lock as part of the release build. Package installation and compatibility on Python 3.12 remain unverified, including transitive dependencies.

Then run `docker compose up -d --build` on a host with Docker, verify the init job, backend health and worker, perform A–E using the browser/API, disconnect the internet while keeping the LAN up, restart the server, verify UNKNOWN recovery rather than replay, and exercise backup/restore against disposable data. Complete actual Android/PWA/thermal-printer tests on the restaurant network before production acceptance.

## Known limits

No physical-print confirmation exists; SENT is transport success. Real text encoding/raster/feed/cutter compatibility needs hardware validation. HTTP LAN mode is a browser app; installable PWA needs trusted HTTPS. No offline order synchronization, refunds, submitted-item voiding, split payment, tax, discounts, gateway verification, or built-in PIN-reset UI. SQLite serializes transactions and is intended for this small restaurant. Data backup does not automatically copy PNG/text previews; retain the ticket directory separately if needed. Sales history without a date is limited to the latest 200 payments; selecting a business date returns that day's history. Empty tables require administrator release. This build is not yet production-validated.

## Code review follow-up

Reviewed backend API/auth, database models and migrations, order/payment services, printer worker/rendering, frontend pages/stores/API, unit/browser tests, Compose/Dockerfiles, and backup/restore tooling. Static review does not substitute for running the full stack.

Fixed findings:

- SQLite backup/restore used connection context managers without closing connections. Explicit closing now releases database handles before file replacement; the online-backup/restore invariant test passes.
- Checkout could retain noncash receipt acknowledgement and an open confirmation after polling changed the bill. Receipt/discard acknowledgement now resets with bill/session/status changes; confirmation is recreated on amount/method/draft changes. Collection is disabled after a failed bill refresh or when another cashier resumes ordering. Added RTL regression coverage, pending dependencies.
- Unicode first-admin setup tokens could cause `compare_digest` to raise TypeError. Compare UTF-8 bytes and return a normal forbidden response; added HTTP regression coverage, pending dependencies.
- Admin base-price editing allowed zero even though full-payment validation requires a positive bill. Item base prices must now be positive; modifier surcharges can remain zero. Empty-session closing also checks submitted quantity instead of total, protecting any legacy zero-price submitted items.

Remaining release blockers: full pytest/Vitest/TypeScript/Playwright execution, dependency locks and audit, Compose startup, actual Android/PWA HTTPS checks, real-printer compatibility. The read path currently also uses BEGIN IMMEDIATE; validate polling load on the actual server before service. Readable formatting should be applied with the configured tools after dependencies are available.

### One-command container verification

From a normal development-machine terminal with internet access and Docker privileges:

```bash
sudo bash scripts/verify-in-docker.sh
```

This uses Python 3.12 and Node 22 images, builds isolated test targets, runs backend and frontend unit tests without network access, and builds production images. It neither starts the restaurant POS nor mounts production data. Logs and generated dependency snapshots go to `artifacts/checks/`; the script stops on any failed command. Browser acceptance remains separate. Test dependencies are in Docker test stages and stay out of production images.

The current managed agent session cannot use sudo, resolve package registries or access the Docker socket. A password does not override those process restrictions. Run this command in the host's ordinary terminal; do not loosen socket permissions to 777. If Docker/pip are missing on another development host, run `bash scripts/install-dev-tools.sh` there first.

Kitchen raster rendering now loads each distinct font size once per ticket, reducing repeated CJK font loading for larger batches.

A further recovery defect was fixed: before-restore copies used the process ID, which is commonly 1 on every container invocation. A second restore would then fail on an existing destination. Copies now use unique random suffixes, and a new repeated-restore regression test passes. Current standalone result: 20 tests (8 invariant tests plus 12 pricing tests). Prior dated counts remain historical.

## Host verification results — 2026-11-04

Read `artifacts/checks/backend-tests.log`: the Python 3.12 Docker backend suite completed with **40 passed**, with one Starlette/AnyIO deprecation warning. This is confirmed host-run evidence; the earlier statements that the full backend suite was pending are now superseded.

The frontend container build failed on three TS2769 errors in `Checkout.test.tsx`: React Testing Library role queries do not accept Playwright's `exact` option. Replaced them with anchored accessible-name regexes. Scanned other source unit tests; no remaining `exact` options. Playwright's valid `exact` options are retained. The corrected frontend build and tests still require rerunning on the host.

To resume only the remaining checks from the repository root:

```bash
sudo docker build --target test -t keke-pos/frontend-check ./frontend
sudo docker run --rm --network none keke-pos/frontend-check
sudo docker compose build
```
