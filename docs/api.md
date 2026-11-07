# API Reference

FastAPI exposes interactive documentation at `/api/docs` and the machine-readable schema at `/api/openapi.json`, both directly and through Nginx. Swagger UI assets are development documentation served from its default CDN; normal POS operation never uses them. JSON requests use `Content-Type: application/json`; authenticated requests require `Authorization: Bearer <token>`.

Success responses are typed objects or lists; HTTP errors use `{"detail":"message"}`; Pydantic validation errors use the standard FastAPI detail list. Invalid input returns 422; unauthenticated 401; forbidden 403; missing resources 404; state/idempotency conflicts 409; throttling 429; database contention 503. Sensitive routes enforce roles on the backend, not only in navigation.

| Method | Path (under `/api`) | Permission / behavior |
| --- | --- | --- |
| GET | `/health` | Public readiness; verifies migrated database |
| GET | `/auth/setup-status` | Public; indicates first-admin setup |
| POST | `/auth/setup` | Public with configured one-time setup token; name and PIN |
| POST | `/auth/login` | Name and PIN; opaque expiring bearer token |
| GET / POST | `/auth/me`, `/auth/logout` | Current identity / revoke session |
| GET / POST | `/users` | Admin; list/create named staff or administrators |
| GET | `/tables`, `/tables/{id}`, `/tables/{id}/active-session` | Staff; status, current session, submitted total and count |
| POST | `/tables/{id}/open` | Staff; atomically create or return existing active session |
| GET | `/menu`, `/menu/items` | Staff; prices, modifier groups/options/defaults |
| PATCH | `/menu/items/{id}` | Admin; `{"price":800}` in integer sen |
| PATCH | `/menu/options/{id}` | Admin; update modifier surcharge |
| POST | `/order-batches` | Staff; `{"session_id":1}`; returns/reuses owned draft |
| POST | `/order-batches/{id}/items` | Owner/admin; validated item; Idempotency-Key required |
| PATCH | `/order-batches/{id}/items/{item_id}` | Unpaid item edit; private drafts owner/admin; revision, expected unit price and Idempotency-Key required |
| POST | `/order-batches/{id}/items/{item_id}/cancel` | Cancel unpaid item; expected item revision, reason and Idempotency-Key |
| PATCH | `/order-batches/{id}/details` | Edit unpaid round notes/manual paid label; expected info revision and Idempotency-Key |
| PATCH | `/table-sessions/{id}/notes` | Edit open table remarks; expected metadata revision and Idempotency-Key |
| POST | `/table-sessions/{id}/cancel` | Cancel unpaid table and drafts; expected bill change token, reason and Idempotency-Key |
| DELETE | `/order-batches/{id}/items/{item_id}` | Owner/admin; cancel draft line only |
| DELETE | `/order-batches/{id}` | Owner/admin; cancel draft |
| POST | `/order-batches/{id}/submit` | Owner/admin; optional `{"notes":"整单备注"}` body; Idempotency-Key required; atomically save/queue |
| GET | `/table-sessions/{id}/orders`, `/table-sessions/{id}/bill` | Staff; batches and authoritative submitted bill |
| POST | `/table-sessions/{id}/checkout`, `/table-sessions/{id}/resume` | Admin; set/clear ordering pause |
| POST | `/table-sessions/{id}/close-empty` | Admin; cancel empty session and drafts |
| POST | `/table-sessions/{id}/payments` | Admin; Idempotency-Key required; one full payment |
| GET | `/print-jobs`, `/print-jobs/{id}` | Staff; recent queue/history and outcome |
| GET | `/print-jobs/{id}/preview` | Staff; authenticated PNG response |
| POST | `/print-jobs/{id}/retry` | Admin; Idempotency-Key required; audited new attempt with REPRINT marker |
| GET / PUT | `/printers/config` | Admin; full validated printer configuration |
| POST | `/printers/test-print` | Admin; queue a test ticket |
| GET | `/reports/daily-sales?day=2026-11-03` | Admin; local-day completed totals and method breakdown |
| GET | `/reports/transactions?day=2026-11-03` | Admin; transactions with full historical bills; without day, latest 200 |
| GET | `/audit-logs` | Admin; latest 200 operational audit entries |

## Request examples

Add a menu item using IDs returned by `/menu` (never assume seed IDs in clients):

```json
{"menu_item_id":1,"quantity":2,"option_ids":[1,5,7]}
```

Pay a current RM29 bill with RM50 cash:

```json
{"method":"CASH","received":5000,"expected_total":2900,"discard_drafts":false}
```

Methods are CASH, QR, OTHER. Noncash received amount is recorded as the full bill; the cashier must verify the external payment manually. Response includes `total`, `received`, `change`, payment ID and timestamp.

Use a stable, random 8–128 character `Idempotency-Key` for each logical add/submit/payment/reprint operation. Retry ambiguous responses using the **same** key and payload. A new batch or changed payment must use a new key. Submission retries return the original job even if its delivery status changed. Reprint creates separate history rather than altering an old job. Draft-add identities are also stored durably. Printing results must be read from print-job endpoints; submitting an order never certifies physical printing.
