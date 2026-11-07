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

Every item has 堂食 / 打包 at the top of its options; choose 打包 for takeaway. Prepared drinks also offer Kosong（不加糖）or Siu Dai（少甜）, with optional Kao（加浓）. Iced drinks offer 少冰 / 去冰; switching to hot clears the ice adjustment. These choices do not add a fee and appear on the appropriate stall ticket and cashier receipt. Bottled/canned drinks, plain water and beer keep only their relevant temperature/package and takeaway choices. See [takeaway and drink options](takeaway-and-drinks.md).

## Cashier checkout

1. Open the table and tap 查看账单 / 收款.
2. Verify every submitted item and 应收总额.
3. 二维码 is selected by default. Verify funds yourself, or choose 现金 or 其他. For cash, enter ringgit, such as `50.00`; the app shows change and rejects insufficient amounts.
4. If drafts remain, go back to submit them or explicitly acknowledge discarding all table drafts.
5. Tap 确认收款并清台 once. The table becomes available, its cashier receipt is queued and the receipt page opens. The completed transaction remains in 营业记录.

For an accidentally opened empty table, an administrator can use 取消草稿并释放空桌. A table with submitted billable items must be paid; staff cannot erase submitted sales.

## Printer trouble

The 订单 page initially shows only unfinished orders. Each card shows its table number, completion status and separate print delivery status. Completion means successful payment and table release; sending a kitchen ticket does not complete the order. Tap 展开已完成订单 to view the latest 100 completed records, including cashier receipts, print errors and reprint actions; tap 收起已完成订单 to hide them again. Reusing a table does not reopen the previous session's completed orders.

Ask the kitchen whether it already received the ticket. The cashier can inspect the preview and status in 订单. Waiting/sending jobs cannot be resent. FAILED means delivery failed before sending; UNKNOWN means it may already have arrived. Use 核实厨房后重印 only after checking; the replacement ticket displays REPRINT / 重印. Do not create another food order to solve a printer failure.

## If WiFi or the server fails

Keep the current page. An error means the submission result may be unknown. Reconnect to the restaurant WiFi, reopen the table and inspect submitted batches and drafts. Retry the same draft, not a newly created duplicate order. The app does not queue offline orders. Follow the owner's paper-order procedure while the server is unavailable, and reconcile carefully before entering orders later.

## Administration

Settings is visible only to administrators. It supports menu and modifier prices, staff creation, printer settings and test printing. New prices apply to new submissions; historical bills retain their original prices. 营业记录 shows completed transactions and cash/QR/other totals for the selected Malaysian business date. There are no refunds, discounts, taxes, split bills or automatic QR verification in this MVP.
