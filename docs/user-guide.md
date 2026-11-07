# Staff Guide

The operational interface defaults to Simplified Chinese. This guide uses English explanations with the exact on-screen labels.

## Open a table and order

1. Sign in with your staff name and PIN.
2. On 桌台, choose T01–T20. Green 空桌 means available; orange 用餐中 means occupied; blue 待结账 means checkout is in progress. Text accompanies every color.
3. Choose a category and dish, such as 云吞面, 面粉粿 or 海南咖喱饭. The screen scrolls to its options. Default options are already selected. Choose sauce/preparation/portion, change quantity using −/+, then tap 加入草稿.
4. Review 当前草稿. It is saved but has **not** reached the kitchen. Use 修改 to change a line's quantity/options/item note. Fill 整单备注（选填） for instructions applying to the whole round; this remark saves with order submission. Remove unwanted lines or confirm 丢弃此草稿 if necessary.
5. Tap 确认下单 / 送档口 once. After the order is saved, the app returns to tables and identifies the queued kitchen/drinks tickets.
6. Check 订单 for the printer result. 已发送至打印机 means sent, not proof of physical printing. If paper is missing, tell the cashier.

To add food, reopen the occupied table and repeat. Existing submitted items remain on the bill. Only the new batch is printed. If checkout is already in progress, ask the cashier to choose 返回继续加单 first.

Opening a table or saving a draft keeps it 空桌; successful order submission marks it 用餐中. Before payment, 修改 is also available on submitted items. Saving creates an audited 更改单 for the affected stall, showing old and new content; notify that stall. Paid transactions cannot be edited. See [order remarks and editing rules](order-editing.md).

After more than 45 minutes from the first submitted order, the table's time becomes bold red and its border flashes red. Tap 已留意 on that card after checking the table or serving the food. The flashing stops for all devices (other phones refresh within 4 seconds); red time/border remain as a duration indicator. This does not open the ordering screen, change the bill or clear the table. A new session after clearing starts without an acknowledgement. Devices requesting reduced motion show a steady red alert instead of animation.

For a customer who cancels after waiting, use 取消此项 beside the food, or 取消整桌 to cancel all remaining unpaid food/drafts and release the table. Select 等候太久 and confirm. The appropriate stalls get cancellation notices; original records remain available. Edit 整桌备注 at any time before payment, or use 修改本轮备注 / 付款标记 for a specific round. 本轮已付款（仅手动标记） is only a label and does not record revenue or release the table. See [table controls and new menu choices](table-controls.md).

整桌备注（所有轮次） is at the bottom of the ordering page, after the bill and any other staff drafts. 小吃 also includes 云吞汤 (10粒, RM8); quantity/takeaway are available and it routes to the noodle stall.

面粉粿 / 面粉糕 offers **汤分开** under 打包设置 only after choosing 打包. It is optional, not selected automatically and has no surcharge. Returning to 堂食 clears it. The selection appears on cart, preparation tickets and receipts; ordinary/large/egg pricing remains unchanged.

Every item has 堂食 / 打包 at the top of its options; choose 打包 for takeaway. Prepared drinks also offer Kosong（不加糖）or Siu Dai（少甜）, with optional Kao（加浓）. Iced drinks offer 少冰 / 去冰; switching to hot clears the ice adjustment. These choices do not add a fee and appear on the appropriate stall ticket and cashier receipt. Bottled/canned drinks, plain water and beer keep only their relevant temperature/package and takeaway choices. See [takeaway and drink options](takeaway-and-drinks.md).

Order/bill lines and new thermal receipts omit the free neutral labels 不加蛋、普通、堂食. The choices stay selected in the editor and stored in history; prices are unchanged. Actual additions and preparation instructions (加蛋、加面、大份、打包、酱汁、辣度、汤/干、冷热 and drink adjustments) remain visible. Correction tickets explicitly show a neutral choice when it reverses an earlier instruction, such as 加蛋→不加蛋 or 打包→堂食. Old rendered preview images are retained as the original print record.

For something outside the menu, use ＋ 自定义餐点 / 价格 below the item list. Enter name, unit price in RM, quantity, category and preparation stall; takeaway and item remarks are available. It joins the current draft and is sent only when you confirm the order. Custom dishes are not added to the fixed menu. Before payment, use 修改 to change their name/price/quantity/notes. Submitted category/stall stay fixed; cancel and re-add to change the destination. Custom beer also asks for bottles per unit/package.

## Cashier checkout

All submitted items marked 打包 change the table card's 用餐中 label to 等待打包. Adding dine-in food changes it back; cancelled items and unsent drafts do not determine this label. A green 已付款 note means every active ordering round has the manual paid-first label. If only some rounds are marked, the card says 部分已付款. These labels do not record a cashier payment or clear the table.

1. Open the table and tap 查看账单 / 收款.
2. Verify every submitted item and 应收总额. For an offer, enter 优惠后总价 (RM) directly (RM0 up to the original total, at most two decimal places). An optional 优惠备注 explains the offer; 恢复原价 removes it. If another device changes the bill total, the input returns to the current original total for review.
3. 二维码 is selected by default. Verify funds yourself, or choose 现金 or 其他. For cash, enter ringgit, such as `50.00`; the app shows change and rejects insufficient amounts.
4. If drafts remain, go back to submit them or explicitly acknowledge discarding all table drafts.
5. Paper receipts are off by default. Tick 打印收据（默认不打印） only if the customer wants one. Tap 确认收款并清台 once: the table becomes available and the saved receipt page opens. You can use 打印收据 there or from 营业记录 later. Viewing/reloading does not print.

Food prices and kitchen tickets retain the original amounts. Customer receipts and transaction history show original total, offer and final payment. Daily sales/cash/QR totals use actual payment; category revenue shares the offer proportionally, rounded in integer sen so categories sum exactly to actual sales. 优惠前金额 and 优惠合计 are shown separately. Only cashiers/admins can record an offer; completed payments remain locked.

For an accidentally opened empty table, an administrator can use 取消草稿并释放空桌. A table with submitted billable items must be paid; staff cannot erase submitted sales.

For an accidentally closed table, the cashier/admin uses **桌台 → 恢复误关桌台**. Select the exact table/date/record, review its food and enter the reason. A cancelled unpaid table restores its previous items/drafts/remarks and sends a clear 恢复单 to affected stalls. Food cancelled individually before the whole-table closure stays cancelled. The original cancellation and print history remain.

For a mistaken 确认收款并清台, use **确认撤销收款并恢复**. POS keeps the original payment/receipt, records its reversal and excludes it from sales, then opens an unpaid session with frozen food prices and notes. No food preparation or cashier receipt is automatically printed again. Original discounts are suggested at checkout when the subtotal is unchanged; review them before collecting again. This corrects POS records and does not refund a bank/QR transfer. Actual cash/funds must be checked separately.

The original receipt shows 收款已撤销 / 原收据作废 and cannot be sent/reprinted from the server. Its original paper/preview and payment remain available as history. A table already used for another customer's food/drafts cannot be overwritten. A never-used empty session created by tapping the empty table may be retired automatically, with its identity retained in the recovery audit.

## Printer trouble

Preparation tickets put **【打包】** on its own larger, bold line. Cancelled items and old correction content have a physical strike-through; replacement content remains normal. Cancellation/restore headers still identify the operation explicitly. On a restore notice, check the original food and avoid preparing/serving it twice.

The 订单 page initially shows only unfinished orders. Each card shows its table number, completion status and separate print delivery status. Completion means successful payment and table release; sending a kitchen ticket does not complete the order. Tap 展开已完成订单 to view the latest 100 completed records, including cashier receipts, print errors and reprint actions; tap 收起已完成订单 to hide them again. Reusing a table does not reopen the previous session's completed orders.

Ask the kitchen whether it already received the ticket. The cashier can inspect the preview and status in 订单. Waiting/sending jobs cannot be resent. FAILED means delivery failed before sending; UNKNOWN means it may already have arrived. Use 核实厨房后重印 only after checking; the replacement ticket displays REPRINT / 重印. Do not create another food order to solve a printer failure.

## If WiFi or the server fails

Keep the current page. An error means the submission result may be unknown. Reconnect to the restaurant WiFi, reopen the table and inspect submitted batches and drafts. Retry the same draft, not a newly created duplicate order. The app does not queue offline orders. Follow the owner's paper-order procedure while the server is unavailable, and reconcile carefully before entering orders later.

## Administration

Settings is visible only to administrators. It supports menu and modifier prices, staff creation, printer settings and test printing. New prices apply to new submissions; historical bills retain their original prices. 营业记录 shows completed transactions and cash/QR/other totals for the selected Malaysian business date. There are no refunds, discounts, taxes, split bills or automatic QR verification in this MVP.
