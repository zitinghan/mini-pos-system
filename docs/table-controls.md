# Cancellations, editable remarks, manual paid labels and drink choices

These controls apply to open, unpaid table sessions. A recorded cashier payment remains locked; this update does not delete sales or add a refund workflow. During checkout, use 继续加单 to resume ordering before changing/cancelling it.

## Table attention and cashier offers

整桌备注 now appears at the bottom of the ordering page. After strictly more than 45 minutes from the first submitted round, an active table has bold red time and a red flashing border. 已留意 stores one acknowledged timestamp per session and stops the flash on every device; it preserves red duration styling and does not change orders, payments or table occupancy. The flag survives refresh/restart and resets for the next table session. Missing/invalid/future first-order times and closed tables do not trigger the alert. Reduced-motion devices keep a steady red border.

Cashier checkout has a directly editable 优惠后总价 (RM), defaulting to the original bill. It supports RM0 through the original amount, optional offer notes and 恢复原价. A changed polled bill returns the input to the new original amount, and the backend still requires the current original `expected_total`. Cash change and QR receipts use the final payment; item snapshots/prices and preparation tickets retain their original values. Original total, actual payment and offer reason are audited, stored and printed on new customer receipts. Paid transactions remain locked.

Daily category revenue allocates an offer in proportion to original category amounts using largest remainders in integer sen. All category amounts add up to actual sales exactly; free water receives no revenue. Original revenue and offer totals are separate metrics. Beer package/bottle quantities are unaffected.

Migration `0008_table_attention` adds the acknowledgement timestamp. `0009_cashier_offer` adds original payment total/offer reason and backfills the original amount from each existing payment, without changing any previous payment amount or receipt snapshot. Idempotent seeding adds 云吞汤 (小吃, 10粒, RM8) once, routed to KITCHEN/面档, with quantity and takeaway options.

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

面粉粿 / 面粉糕 now has an optional **汤分开** choice under 打包设置. It is free and unselected initially. The picker shows it only after 打包 and clears it on returning to 堂食; the backend requires explicit takeaway even when older clients omit the default dine-in choice. It is available only on this dish. The selected instruction is snapshotted, printed on the preparation ticket and retained on bills/receipts/history. Removing it from an unpaid submitted item prints a correction with the old instruction struck through. Idempotent seed adds one group/option/link; existing prices, enabled states, incompatibilities and historical records are preserved without schema changes.

面粉粿 has 普通 RM8 / 大份 RM10, with egg adding RM1 (RM9 / RM11). The new portion group accepts omission for existing phones/drafts, meaning regular, and repeated seeding preserves configured prices.

汽水 / 罐装 has one optional 品牌 / 口味 choice: **Sprite, Coke, Fanta, 100 PLUS, 菊花茶, 7UP, Passion Fruit**. No brand is automatically selected or printed. Each choice has no surcharge and uses the existing configured Hot/Iced price (initially RM3/RM3.30). Selected names appear on cart, bill, beverage ticket and customer receipt. Existing Hot/Iced administrator-verification flags are retained.

## Data upgrade

Migration `0010_payment_reversals` adds a separate reversal ledger. Paid-table recovery preserves every original payment, receipt, order, timestamp and ticket. It creates a reversal linked to a new unpaid session with cloned submitted snapshots (not current menu prices); prior manual paid labels are cleared on those cloned rounds. The original discount/reason is offered again if the subtotal is unchanged. Reversed payments are excluded from sales/completed-session/dining/category statistics by original payment date; transaction history retains and labels them. Re-paying the restored session records one new valid sale. Replaying an old voided payment is rejected, and replaying the restore request does not create additional sessions or reversals.

Unpaid cancellation recovery uses the closure's audited before-snapshot. Original item IDs/prices/notes are retained, statuses restored and revisions advanced; previously cancelled individual items remain cancelled. New close-empty operations now snapshot drafts for recovery. Legacy closures without a reliable snapshot are blocked. Existing prepared food gets RESTORE notices, not duplicate NEW orders. Restoring a paid table does not resend preparation.

Recovery refuses to overwrite another active customer/draft. Only a never-used shell without batches/notes/first-order/payment may be retired. It blocks while a cashier receipt is SENDING; unsent PENDING receipt jobs are preserved as FAILED with an explicit reversal reason, preventing stale paper delivery. Voided receipts cannot be printed/retried through the server. A network write already completed cannot be physically recalled.

Table display adds 等待打包 when all submitted items are takeaway, and green 已付款 / 部分已付款 according to manual paid-first round labels. Unsubmitted/cancelled rows are excluded. Neither display label changes financial/table-state workflows. Takeaway preparation labels render separately at 64px with bold strokes. Old UPDATE content and CANCEL item details carry strike-through in raster output; text-mode jobs with strike-through use raster so the decoration is retained.

Custom ordering uses one inactive internal SKU, `CUSTOM_ORDER_ITEM`, to preserve existing order-item foreign keys. It is excluded from the menu and standard menu-item ordering; each custom order snapshots its own name, integer-sen unit price, quantity, category, stall, takeaway/notes and optional beer bottle count. Names and prices are never written as new public menu products. The seed adds this internal reference once, without schema changes or altering production records/prices.

`POST /order-batches/{id}/custom-items` requires a draft owner/admin and an idempotency key; retries cannot create duplicate items. All staff may edit submitted unpaid custom items using the custom PATCH endpoint and expected revision. Category/stall are fixed after submission to avoid misdirecting existing preparation; cancel/re-add to move a dish. Corrections show the old and new names/notes/takeaway instructions, and original tickets remain immutable. Checkout/paid locks, cancellation, mixed-category reports, cashier offers and manual receipt printing apply to custom rows.

Cashier receipts now default to **no paper**. The payment transaction still saves its immutable receipt; `print_receipt=true` opts in to one original print job, or the cashier may request that same original later from the receipt page/history. Viewing/reloading and replaying a default payment create no print job. Existing preparation tickets continue to queue on submission. No pending or historical printer jobs are deleted by this preference change.

Migration `0007_table_controls` adds table remarks/revisions, round paid-label/revision fields, cancellation reasons and session links on print jobs. Old print-job session links are backfilled from their batch/payment, without changing original payloads, delivery status or amounts. Idempotent seeding adds only missing 面粉粿 portions and canned brand choices. Existing menu prices, stock, promotions, paid history and printer configuration are preserved.

## Verification

汤分开 update: 94 focused backend cases (menu pricing, takeaway rules and submitted-item edits), all 40 frontend tests, the production build and 3 Android browser cases passed. Verification includes RM8/9/10/11 pricing, omitted legacy choices, rejecting soup separation without takeaway, switching back to dine-in, correction strike-through and receipt snapshots. Repeated seed on a backup preserves every original record/setting and adds exactly one group, one option and their item link.

The concurrent B1 customer-display commit was merged without replacing either feature. The merged version passed 29 additional backend receipt/display/offer/soup checks, 40 frontend tests, a production build and 9 Android checkout/browser cases. Browser hardware configuration is isolated from the restaurant's serial display.

Recovery/takeaway update: the full **246 backend tests**, **39 frontend tests**, production build and **9 Android browser cases** passed. Paid recovery was rechecked after removing unnecessary submission keys from cloned batches. Browser checks cover cancelled-table restoration, green paid-first notes, 等待打包, financial reversal without double sales, original receipt voiding, discount recovery and standard checkout at 360/390/412 widths. Raster previews confirm larger bold takeaway labels and strike-through on old/cancelled content; no live printer output is claimed. A twice-run migration/seed on a current restaurant backup preserved every original record/settings field and created only an empty reversal table.

Custom items and optional cashier printing: **231 backend tests passed**, **38 frontend tests passed**, and the production build passed. Across 360/390/412-pixel Android screens, 12 focused browser cases were verified (11 passed in the main run; the remaining cash-receipt preview case passed after its test explicitly opted in to paper printing). Checks cover manual prices/quantities, stall routing, edits/cancellations, immutable receipts, default no-paper checkout, late first printing, opt-in printing, and original checkout/remark workflows. Repeated seed/upgrade on a database copy preserved every original table/record/settings field and added only one inactive catalog reference. No schema migration is needed for this update.

The table-attention/cashier-offer update was verified on 2026-11-07 with all 224 backend cases (218 passed in the full run; 6 passed on recheck after updating migration/menu-count assertions and explicit UTF-8 test-file reads), 34 frontend tests and a production build. Twelve focused browser checks passed across Android widths 360/390/412, covering alerts, acknowledgement after reload, bottom-positioned remarks, the new snack, cashier offers, normal checkout and editable/cancelled orders. Three additional alert checks passed after shortening the mobile acknowledgement text. A twice-run migration/seed on a copy preserved every original record/settings field and added only the new snack configuration.

Verified on 2026-11-07: the full backend regression suite passed 208 tests; the subsequently added canned-brand test passed separately (209 backend cases in total). All 29 frontend unit tests and the production build passed. Browser checks covered all 30 scenarios across Android widths 360/390/412: 24 existing checks passed initially, followed by 9 passing focused checks including the corrected login wait in the new test harness. These runs overlap on 3 baseline cases.

The upgrade was rehearsed twice on an SQLite copy, preserving original records and existing menu/printer settings. Cancellation and remark tickets were verified with the mock printer; physical printer output still requires hardware validation. No sample orders were submitted to the live restaurant database.
