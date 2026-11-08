# Order and receipt numbers

Submitted orders keep the existing `#123` numeric format. The sequence starts at
`#1` for each new business day at **12:00 noon, Asia/Kuala_Lumpur**. Midnight
does not reset it. A draft gets its number when submitted, so drafts created
before noon and submitted afterward use the new business day's sequence.

One submitted batch has one order number across its kitchen, rice and beverage
tickets. Add-on submissions get the next number. Cancellation does not reuse
numbers, and reprints retain the original snapshot's number.

Historical submitted orders keep their old numbers. On installation, new orders
continue after the highest existing number for the current business day; the
first noon rollover starts the fresh sequence. Database identities never reset.
Orders from different days can share the visible number; dates and permanent
identities still distinguish them.

Receipt/invoice numbers retain the existing continuous `R000001` format and
never reset at noon, midnight, or year-end. Existing receipt snapshots are not
renumbered. The noon rollover does not clear active tables or delete history.
