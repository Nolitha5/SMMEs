# Using SME Operations with real business data

SME Operations does not need generated or synthetic business records for normal use. The workspace should be fed from a real business's operating records.

## Where real data should come from

- Sales: POS export, till system, e-commerce export, or a maintained sales spreadsheet.
- Products: POS product catalogue, inventory workbook, or stock master list.
- Inventory: physical stock counts, stock-on-hand reports, reserved stock, damaged stock and stock already ordered.
- Suppliers and procurement: supplier quotes, invoices, purchase orders, lead times and delivery records.
- Pricing: your current sell price, product cost and real competitor price observations.
- Customers: consented CRM or loyalty records. Do not upload unnecessary personal data.
- Feedback: actual surveys, complaints, reviews or consented customer messages.
- Promotions and events: the business promotion calendar and real local events that can affect demand.

## Exact Demand CSV format already supported

The Demand domain currently understands five CSV files. Empty header-only templates are included in `data-templates/`.

### transactions.csv
`transaction_id,timestamp,store_id,product_id,qty,unit_price,discount,channel`

Use one row per real sale line or aggregated product sale record. Keep `product_id` consistent with `products.csv`.

### products.csv
`product_id,name,category,unit_cost,sell_price,shelf_life_days,active`

Use the real product catalogue. `unit_cost` is the cost to the business; `sell_price` is the current selling price.

### promotions.csv
`promo_id,product_id,start,end,discount_type,value,channel`

Only enter promotions that actually ran or are genuinely scheduled.

### local_events.csv
`event_id,date,day_name,event_name,location,event_type,expected_impact`

Use real events. `expected_impact` is a business estimate and should be based on local knowledge when no historical evidence exists.

### calendar.csv
`date,day_of_week,day_name,day_of_month,month,month_name,is_weekend,is_payday_window`

This is operational calendar context. It can be prepared from the real dates covered by the sales history.

## How much data to collect

For Demand, the implementation can produce a basic result from 7 clean observations, but 28 to 60+ days of real sales history is much more useful because seasonality and stronger forecasting models need more history.

For a useful pilot, start with 5 to 20 products and at least 30 to 60 days of actual transactions.

## Important: current shared workspace intake

The shared web application currently reads processed operational results from the live workspace and lets you review recommendations. It does not yet expose a raw CSV upload screen. Do not paste business data directly into random Firestore collections.

The safe real-data workflow is:

1. Export the real source data from the business.
2. Validate it against the supported input format.
3. Run it through the domain intake/orchestration layer.
4. Publish validated agent results into the shared workspace.
5. Use SME Operations to review results, recommendations, approvals and activity.

Until a dedicated import screen is added, keep the original CSV exports outside the repository and do not commit customer or business-sensitive data to GitHub.

## Do not generate production data

Generated data is useful only for software tests. It should not be mixed with a real business workspace. For a genuine demonstration, use a small pilot business or a real sales/stock spreadsheet with permission from the owner.
