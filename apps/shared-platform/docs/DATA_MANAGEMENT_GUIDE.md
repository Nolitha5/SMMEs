# Business data intake

The Business data area is for real operating records. It does not create synthetic sales, stock, customers, suppliers or prices.

## What users can do

- Import a CSV file in bulk.
- Download an empty CSV template for any supported data set.
- Preview and validate a file before anything is saved.
- Add one record manually.
- Edit an existing record when a correction is needed.
- Keep record identity fields locked while editing so one record cannot silently become another.

Imports use the record ID as the match key. A new ID adds a record. A matching ID updates the existing record.

## Recommended first setup order

1. Products
2. Suppliers and customers, if the business uses them
3. Sales
4. Stock counts and stock movements
5. Supplier quotes and supplier performance
6. Competitor prices
7. Promotions and local events
8. Purchase orders, goods receipts and supplier invoices when available
9. Feedback and customer interactions

References are checked. For example, a sale cannot be imported for a product ID that does not exist in Products.

## Where the real data normally comes from

- Products: POS catalogue, stock workbook or product master.
- Sales: till or POS export, e commerce export, or maintained sales spreadsheet.
- Stock: physical stock count, inventory report and stock movement log.
- Suppliers: supplier master, quotes, purchase orders, delivery records and invoices.
- Pricing: current product cost and selling price plus real competitor observations.
- Customers: consented CRM or loyalty records only.
- Feedback: actual complaints, surveys, reviews and messages the business is allowed to use.
- Promotions and local events: actual campaigns and real events that can affect trading.

## Excel users

Open the workbook, keep the required columns, then save or export the sheet as CSV UTF 8. Use the Template button in the app when the business does not already have matching column names.

## Privacy

Do not collect personal information just because a field exists. Customer IDs can be pseudonymous. Only import contact details when the business has a legitimate operational purpose and permission to use them.

## Important processing note

This intake area saves validated source records into the shared workspace. It does not invent agent results. Agent results should only appear after the real processing pipeline runs against these records.
