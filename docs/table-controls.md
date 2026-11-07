# Cancellations, editable remarks, manual paid labels and drink choices

These controls apply to open, unpaid table sessions. A recorded cashier payment remains locked; this update does not delete sales or add a refund workflow. During checkout, use 继续加单 to resume ordering before changing/cancelling it.

## Cancel one item or the whole table

On the table page, **取消此项** removes a submitted item from the payable bill. Choose a reason (including 等候太久) and confirm once. The item stays in history with its original name/options/price, a CANCELLED state, a revision and its reason; its original print ticket stays unchanged. Only the affected stall receives a **取消单 / CANCEL — 停止制作 / 不要出餐**. Draft items can still be removed before submission without sending a cancellation ticket.

**取消整桌** cancels all remaining unpaid submitted items and all staff drafts, closes the session and releases the table. One cancellation ticket per nonempty affected stall covers all remaining rounds; items already cancelled are not sent again, and drafts never appear on stall cancellation tickets. No payment or sale is created. The reason, actor and full before/after operation are retained. Reopening the same table starts a new session.

Item cancellation requires the latest item revision. Whole-table cancellation uses a bill change token covering submitted/draft batches, item revisions/statuses/amounts, remarks and labels, including zero-price water. If another device changes the table after review, cancellation is rejected for a fresh review. Database changes, audit and cancellation outboxes commit atomically; a print-outbox failure rolls them all back. Retry the same request key after a lost response instead of submitting a new cancellation.

## Edit whole-table and per-round remarks

**整桌备注（所有轮次） → 保存整桌备注** applies instructions to the whole table and subsequent ordering rounds. It can be saved before or after placing food. **修改本轮备注 / 付款标记** edits an already submitted round. Existing draft 整单备注 still saves with that round's submission.

For existing submitted food, these changes send a **备注 / 标记更新** notice to relevant stalls. It explicitly says **只更新提示，请勿重复制作** and contains no new food items. New preparation/correction/cancellation tickets carry the latest appropriate remarks. Current bills, history and newly saved customer receipts show table remarks. Paid receipt snapshots and prior print payloads are not rewritten.

## Manual paid-first label

Check **本轮已付款（仅手动标记）** when submitting a round, or edit it later using 修改本轮备注 / 付款标记. It prints **已付款（手动标记）** and appears on the round/order card. It does not create a Payment, change daily revenue, clear the table or hide an uncompleted preparation order. Add-on rounds default to unmarked; earlier labels are not copied to later food.

At cashier checkout, the screen reminds staff to check previously collected funds and avoid collecting twice. Complete the existing cashier record when settling the table. If cancelling an order that was manually marked paid, handle any funds already collected outside this label; cancellation does not automatically register a payment/refund.

## Menu additions

面粉粿 has 普通 RM8 / 大份 RM10, with egg adding RM1 (RM9 / RM11). The new portion group accepts omission for existing phones/drafts, meaning regular, and repeated seeding preserves configured prices.

汽水 / 罐装 has one optional 品牌 / 口味 choice: **Sprite, Coke, Fanta, 100 PLUS, 菊花茶, 7UP, Passion Fruit**. No brand is automatically selected or printed. Each choice has no surcharge and uses the existing configured Hot/Iced price (initially RM3/RM3.30). Selected names appear on cart, bill, beverage ticket and customer receipt. Existing Hot/Iced administrator-verification flags are retained.

## Data upgrade

Migration `0007_table_controls` adds table remarks/revisions, round paid-label/revision fields, cancellation reasons and session links on print jobs. Old print-job session links are backfilled from their batch/payment, without changing original payloads, delivery status or amounts. Idempotent seeding adds only missing 面粉粿 portions and canned brand choices. Existing menu prices, stock, promotions, paid history and printer configuration are preserved.

## Verification

Verified on 2026-11-07: the full backend regression suite passed 208 tests; the subsequently added canned-brand test passed separately (209 backend cases in total). All 29 frontend unit tests and the production build passed. Browser checks covered all 30 scenarios across Android widths 360/390/412: 24 existing checks passed initially, followed by 9 passing focused checks including the corrected login wait in the new test harness. These runs overlap on 3 baseline cases.

The upgrade was rehearsed twice on an SQLite copy, preserving original records and existing menu/printer settings. Cancellation and remark tickets were verified with the mock printer; physical printer output still requires hardware validation. No sample orders were submitted to the live restaurant database.
