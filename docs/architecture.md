# Architecture

## Runtime

Android browsers connect to Nginx, which serves bundled React assets and proxies same-origin `/api` traffic to FastAPI. React Router provides screens; TanStack Query polls authoritative server state every four seconds; Zustand stores authentication and transient notices. Persistent drafts live in SQLite, not only in a phone's memory.

FastAPI uses SQLAlchemy 2 and Pydantic 2. Alembic applies safe versioned migrations; an idempotent, transactional seed installs T01–T20, 33 menu products, contextual modifiers and the default mock configuration. Startup never resets existing data. A separate process consumes the transactional print outbox. Windows launchers serve the same API/static bundle locally; container services share one `/data` volume for the WAL database and ticket previews.

```mermaid
flowchart LR
  Phone[Android browsers] --> Web[Nginx / React]
  Web --> API[FastAPI]
  API --> DB[(SQLite WAL)]
  DB --> Worker[Print worker]
  Worker --> Mock[PNG / text previews]
  Worker --> Printer[LAN ESC/POS printer]
```

## Persistence

| Tables | Purpose and constraints |
| --- | --- |
| `users`, `auth_sessions`, `login_attempts` | Versioned scrypt PIN hashes (N=32768, r=8, p=3), hashed opaque tokens, expiration and persistent throttling |
| `restaurant_tables`, `table_sessions` | Twenty table identities; one shared active draft/ordering session per table; displayed occupancy begins at first submission |
| `menu_categories`, `menu_items` | Database-controlled category and base prices |
| `modifier_groups`, `modifier_options`, `menu_item_modifier_groups` | Ordered options, minimum/maximum counts, default choices, integer-sen surcharges |
| `order_batches` | DRAFT/SUBMITTED/CANCELLED, globally unique submission key, one draft per user/session |
| `order_items`, `order_item_modifiers` | Revisioned unpaid item snapshots; submitted edits retain before/after audits and immutable correction tickets; paid snapshots are locked |
| `payments` | Unique session and idempotency key, request fingerprint, cashier, payment method, received amount and change |
| `print_jobs`, `printer_configurations` | Immutable ticket payload, delivery state, attempt history, previews and configurable adapter |
| `audit_logs` | Draft-add request identities, payment, menu changes, staff creation, configuration and reprint actor information |

All records except the throttle counter have created/updated UTC ISO timestamps. Reporting converts local-day bounds from Asia/Kuala_Lumpur to UTC. All monetary calculations use integer sen.

## Consistency decisions

SQLite connections enforce foreign keys, WAL and a 15-second busy timeout. Transactions explicitly use `BEGIN IMMEDIATE`: the tiny restaurant workload favors straightforward correctness and serialized writes over throughput. Read transactions also take this lock, so this design targets a few devices, not large chains. No database transaction is held during network printing or raster rendering.

Submitting revalidates modifiers and current prices, saves the round remark, marks the batch submitted and inserts separate nonempty stall print jobs in one commit. New batches contain only incremental items. Unpaid item edits use optimistic revisions, expected prices, idempotency and atomic correction outboxes; old print snapshots remain immutable. UI carts display provisional prices; final prices come from the server. See [order-editing details](order-editing.md).

Payment validates the current submitted total against `expected_total`. It rejects insufficient cash and unacknowledged drafts. One transaction records the payment, cancels explicitly discarded drafts and releases the table. Unique constraints plus request fingerprints prevent duplicate or conflicting payments. Checkout sets PAYMENT_PENDING and blocks additional ordering until cashier resume. Unused empty sessions can be cancelled by an administrator.

## Assumptions and scope

MYR, no tax, discounts, service charge, refunds, split bills or partial payments. QR and other payments are manually confirmed; no payment gateway or automatic verification exists. Unpaid submitted items/tables can be cancelled with retained snapshots, reason/actor audits and cancellation notices; actual paid transactions remain locked. Manual paid-first labels are metadata and never create payments. Staff PIN reset is outside this MVP. Staff use named accounts; PINs have 6–12 ASCII digits. Session tokens expire after 12 hours by default and are revoked on logout. Server and printer remain on a trusted LAN; trusted HTTPS is recommended for credentials and required for Android installable PWA behavior.

Implementation references: [SQLAlchemy SQLite transactions](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) and [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/).

PIN hash parameters follow an [OWASP scrypt configuration](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#scrypt); benchmark login latency on the target server.
