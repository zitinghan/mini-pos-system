# Order remarks, unpaid item edits and table availability

The table list stays green/空桌 when someone only opens a table or saves a draft. The server keeps the shared draft session so multiple phones do not create competing sessions. The first successful order submission changes the displayed table state to 用餐中 and sets `first_order_at`; failed submissions do neither. Zero-price plain water still counts as an order. Payment completion releases the table as before.

The draft section has an **整单备注（选填）** field, up to 500 characters, saved atomically with **确认下单 / 送档口**. Each submitted round can have a different remark. The remark appears on all nonempty stall tickets for that round, the session/bill, order cards, history and customer receipt. Item-specific notes remain separate (up to 240 characters).

Each editable line has **修改**. Its picker opens with the original quantity/options/item note and supports the same takeaway and drink controls as new items. Saving a draft line updates the draft without printing. Before payment, submitted lines can also change quantity, options and notes. Closing the editor or tapping its backdrop discards unsaved edits. Paid history remains locked; checkout must be resumed before further changes.

Submitted changes create a separate **UPDATE / 更改单** for only the affected stall. It identifies the table, original order batch, unique ticket/change references and timestamp, then prints **原内容（作废）** and **改为以下内容**. It preserves the original ticket and records complete before/after item snapshots in the audit log. Staff should notify the affected stall. A reprint preserves the correction reference and adds the existing REPRINT marking.

Notes, quantity and free-option changes preserve the submitted unit price. Changing a priced portion or temperature/package uses current backend configuration; the editor shows the resulting unit/line price. Backend `expected_unit_price` guards against price changes while editing. Previously submitted sold-out items can reduce quantity or update unchanged-option notes; increases require availability. Selecting another dish and cancelling a submitted line remain separate operations; the editor handles the existing dish at quantities 1–99.

`PATCH /api/order-batches/{batch_id}/items/{item_id}` requires an Idempotency-Key, item payload, `expected_revision` and `expected_unit_price`. Concurrent edits with a stale revision fail instead of overwriting. Replaying an accepted request returns its stored result even after payment without sending another correction. An outbox failure rolls the item/modifiers/revision/audit back together. The worker waits for earlier pending/sending tickets for the same batch/stall before sending a correction. It never equates a network write with paper output.

Migration `0006_order_editing` safely adds batch notes, item revisions (starting at 1), correction-to-audit references on print jobs, and a separate active-correction index. It preserves all original financial/order/print snapshots. Existing API submit calls without a notes body continue to work. Receipt snapshots now include per-round remarks; previously paid receipt snapshots are not rewritten.

## Verification — 2026-11-07

- Full backend regression: **196 passed**; separate multiline-remark/correction rendering regression: **1 passed**. One existing Starlette/AnyIO deprecation warning remains.
- Frontend: **27 passed**; production TypeScript/Vite build passed.
- Browser: **21 passed** at 360/390/412 pixels, including draft-only table availability, first-submit occupancy, draft and submitted edits, outside-click editor dismissal, per-round remarks, correction cards, takeaway/drink modifiers, payment receipts and existing workflows.
- Migration/seed rehearsal passed on a production backup. The stopped live upgrade and repeated seed preserved all pre-existing users, sessions, batches/items/modifier snapshots, payments, print jobs, audit records, receipt snapshots, old menu/option prices, stock, promotions, table identities and printer configuration. No live sample orders or test print jobs were created.
- Added 33 packing groups and sweetness/strength/ice groups for 13 prepared drinks. The 80mm preparation / 55mm cashier configurations remain unchanged. Mobile screenshots and an 80mm multiline correction raster preview were inspected; physical printer output was not tested by this update.
