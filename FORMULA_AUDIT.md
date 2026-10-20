# BizPulse: Complete Formula, Financial Logic & Data Accuracy Audit

## Calculation Inventory & Audit Specifications

This document catalogs every mathematical equation, financial formula, numerical calculation, business rule, database aggregation, KPI, and derived metric discovered and verified in BizPulse.

---

### CALC-001: Sales Line Item Subtotal
* **Feature Name**: Sales Bill Book Line Item
* **Business Definition**: Net customer payable for a single line item after subtracting discounts from gross rate.
* **Source File & Function**: `sales/models.py:SaleItem.calculate_line_total` & `sales/services.py:create_sale_bill`
* **Source Database Fields**: `sales_saleitem.quantity_sold`, `sales_saleitem.actual_selling_price_per_unit`, `sales_saleitem.discount_amount`
* **Formula Currently Used**:
  $$\text{Line Total} = \max\left((\text{Quantity Sold} \times \text{Selling Price Per Unit}) - \text{Discount Amount},\; 0.00\right).\text{quantize}(0.01, \text{ROUND\_HALF\_UP})$$
* **Assumptions**: Discounts cannot exceed gross line amount; monetary values quantized to two decimal places using standard half-up financial rounding.
* **Example Inputs**: Quantity = 1.25, Price = ₹12.33, Discount = ₹1.00.
* **Expected Result**: $(1.25 \times 12.33) - 1.00 = 15.4125 - 1.00 = 14.4125 \xrightarrow{\text{round}} 14.41$.
* **Actual Tested Result**: `14.41`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_line_total_quantization_and_rounding`
* **Status**: **PASS** (Defect corrected: unquantized float-subtotal in `create_sale_bill` replaced with strict `ROUND_HALF_UP` quantization).

---

### CALC-002: Sales Bill Total Amount
* **Feature Name**: Sales Bill Grand Total
* **Business Definition**: Total invoice amount payable by the customer for all items on a bill.
* **Source File & Function**: `sales/models.py:Sale.calculate_total` & `sales/services.py:create_sale_bill`
* **Source Database Fields**: `sales_saleitem.line_total`
* **Formula Currently Used**:
  $$\text{Total Bill Amount} = \sum_{i=1}^{n} \text{line\_total}_i$$
* **Assumptions**: A bill must have at least one line item; line items cannot be duplicate-aggregated.
* **Example Inputs**: Line 1 = ₹150.00, Line 2 = ₹240.00.
* **Expected Result**: $150.00 + 240.00 = 390.00$.
* **Actual Tested Result**: `390.00`.
* **Test Name**: `tests.test_sales.SaleServiceTests.test_create_sale_bill_success`
* **Status**: **PASS**.

---

### CALC-003: Sales Bill Outstanding Dues & Payment Status
* **Feature Name**: Customer Bill Dues & Credit Tracking
* **Business Definition**: Remaining unpaid balance due from a customer on a sales bill.
* **Source File & Function**: `sales/models.py:Sale.save` & `sales/services.py:create_sale_bill`
* **Source Database Fields**: `sales_sale.total_amount`, `sales_sale.amount_paid`
* **Formula Currently Used**:
  $$\text{Outstanding Amount} = \max\left(\text{total\_amount} - \text{amount\_paid},\; 0.00\right)$$
  $$\text{Payment Status} = \begin{cases} \text{'paid'} & \text{if } \text{amount\_paid} \ge \text{total\_amount} > 0 \\ \text{'partial'} & \text{if } 0 < \text{amount\_paid} < \text{total\_amount} \\ \text{'unpaid'} & \text{if } \text{amount\_paid} = 0 \end{cases}$$
* **Assumptions**: Amount paid cannot exceed total bill amount; status automatically synchronizes on model save.
* **Example Inputs**: Total Amount = ₹500.00, Amount Paid = ₹300.00.
* **Expected Result**: Outstanding = ₹200.00, Status = 'partial'.
* **Actual Tested Result**: Outstanding = `200.00`, Status = `'partial'`.
* **Test Name**: `tests.test_audit_edge_cases.AuditEdgeCasesTests.test_partial_payment_and_outstanding_balance_reconciliation`
* **Status**: **PASS** (Defect corrected: auto-synchronization added to `Sale.save()` to guarantee model-level integrity).

---

### CALC-004: Purchase Line Item Total
* **Feature Name**: Purchase Invoice Line Total
* **Business Definition**: Cost payable to supplier for a single inventory item line.
* **Source File & Function**: `purchases/models.py:PurchaseItem.calculate_line_total` & `purchases/services.py:create_purchase_order`
* **Source Database Fields**: `purchases_purchaseitem.quantity_purchased`, `purchases_purchaseitem.purchase_cost_per_unit`
* **Formula Currently Used**:
  $$\text{Line Total} = (\text{Quantity Purchased} \times \text{Purchase Cost Per Unit}).\text{quantize}(0.01, \text{ROUND\_HALF\_UP})$$
* **Assumptions**: Quantity > 0; cost $\ge$ 0; quantized to 2 decimal places.
* **Example Inputs**: Quantity = 14.00, Cost = ₹200.00.
* **Expected Result**: $14.00 \times 200.00 = 2,800.00$.
* **Actual Tested Result**: `2800.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS**.

---

### CALC-005: Purchase Order Total Amount
* **Feature Name**: Supplier Invoice Total
* **Business Definition**: Total gross expenditure committed to a supplier for incoming stock.
* **Source File & Function**: `purchases/models.py:Purchase.calculate_total` & `purchases/services.py:create_purchase_order`
* **Source Database Fields**: `purchases_purchaseitem.line_total`
* **Formula Currently Used**:
  $$\text{Total Purchase Amount} = \sum_{i=1}^{n} \text{line\_total}_i$$
* **Assumptions**: Invoices with multiple items sum all valid line totals.
* **Example Inputs**: Item 1 = ₹1,000.00, Item 2 = ₹700.00.
* **Expected Result**: $1,000.00 + 700.00 = 1,700.00$.
* **Actual Tested Result**: `1700.00`.
* **Test Name**: `tests.test_csv_uploads.CSVUploadTests.test_purchases_csv_upload_valid_and_grouped`
* **Status**: **PASS**.

---

### CALC-006: Purchase Outstanding Payables & Payment Status
* **Feature Name**: Supplier Payables Tracking
* **Business Definition**: Debt owed to a supplier for credit purchases.
* **Source File & Function**: `purchases/models.py:Purchase.save` & `purchases/services.py:create_purchase_order`
* **Source Database Fields**: `purchases_purchase.total_amount`, `purchases_purchase.amount_paid`
* **Formula Currently Used**:
  $$\text{Outstanding Amount} = \max\left(\text{total\_amount} - \text{amount\_paid},\; 0.00\right)$$
* **Assumptions**: `amount_paid` $\le$ `total_amount`; `total_amount = amount_paid + outstanding_amount` invariant strictly held.
* **Example Inputs**: Total Amount = ₹1,200.00, Amount Paid = ₹800.00.
* **Expected Result**: Outstanding = ₹400.00, Status = 'partial'.
* **Actual Tested Result**: Outstanding = `400.00`, Status = `'partial'`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`
* **Status**: **PASS** (Defect corrected: auto-synchronization added to `Purchase.save()`).

---

### CALC-007: Moving Weighted-Average Inventory Unit Cost (Purchase Inflow)
* **Feature Name**: Weighted-Average Inventory Costing (Perpetual Moving Average)
* **Business Definition**: Recalculates unit valuation on every stock addition to conform with AS-2 / GAAP perpetual inventory costing.
* **Source File & Function**: `purchases/services.py:create_purchase_order` & `inventory/csv_services.py:import_products_from_csv`
* **Source Database Fields**: `inventory_product.current_stock`, `inventory_product.weighted_avg_cost`, `purchases_purchaseitem.quantity_purchased`, `purchases_purchaseitem.purchase_cost_per_unit`
* **Formula Currently Used**:
  $$\text{New Weighted Average Cost} = \begin{cases} \frac{(\text{Current Stock} \times \text{Current Avg Cost}) + (\text{Qty Purchased} \times \text{Unit Cost})}{\text{Current Stock} + \text{Qty Purchased}} & \text{if } \text{Current Stock} > 0 \\ \text{Unit Cost} & \text{if } \text{Current Stock} \le 0 \end{cases}$$
* **Assumptions**: Evaluated immediately prior to creating the positive stock movement record; stored to 4 decimal places (`NUMERIC(12, 4)`) to avoid rounding error buildup.
* **Example Inputs**: Current Stock = 6 units @ ₹100.00, Incoming = 14 units @ ₹200.00.
* **Expected Result**: $\frac{(6 \times 100.00) + (14 \times 200.00)}{6 + 14} = \frac{600 + 2800}{20} = \frac{3400}{20} = 170.0000$.
* **Actual Tested Result**: `170.0000`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS** (Defect corrected: applied to `inventory/csv_services.py` for bulk imports).

---

### CALC-008: Moving Weighted-Average Inventory Unit Cost (Purchase Voiding Reversal)
* **Feature Name**: Weighted-Average Cost Reversal upon Purchase Cancellation
* **Business Definition**: Restores prior inventory cost baseline when an erroneous purchase invoice is voided.
* **Source File & Function**: `purchases/services.py:void_purchase_order`
* **Source Database Fields**: `inventory_product.current_stock`, `inventory_product.weighted_avg_cost`, `purchases_purchaseitem.quantity_purchased`, `purchases_purchaseitem.purchase_cost_per_unit`
* **Formula Currently Used**:
  $$\text{Remaining Stock} = \text{Current Stock} - \text{Qty Voided}$$
  $$\text{Restored Weighted Avg Cost} = \begin{cases} \frac{(\text{Current Stock} \times \text{Weighted Avg Cost}) - (\text{Qty Voided} \times \text{Purchase Cost})}{\text{Remaining Stock}} & \text{if } \text{Remaining Stock} > 0 \\ \text{purchase\_cost\_per\_unit} & \text{if } \text{Remaining Stock} \le 0 \end{cases}$$
* **Assumptions**: Cannot void a purchase if remaining stock would drop below zero (goods already sold).
* **Example Inputs**: Current Stock = 20 units @ ₹100.00, Voiding 10 units @ ₹150.00.
* **Expected Result**: $\frac{(20 \times 100) - (10 \times 150)}{10} = \frac{2000 - 1500}{10} = \frac{500}{10} = 50.0000$.
* **Actual Tested Result**: `50.0000`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_purchase_voiding_restores_prior_weighted_avg_cost`
* **Status**: **PASS** (Critical defect corrected: prevented permanent cost contamination from cancelled purchases).

---

### CALC-009: Current Physical Stock Balance
* **Feature Name**: Product Stock Level Tracking
* **Business Definition**: Authoritative inventory balance derived from the complete ledger of immutable stock movements.
* **Source File & Function**: `inventory/models.py:Product.current_stock`
* **Source Database Fields**: `inventory_stockmovement.quantity`
* **Formula Currently Used**:
  $$\text{Current Stock} = \sum \text{StockMovement.quantity}$$
  $$\text{Where: } \text{Quantity} > 0 \text{ for IN (OPENING, PURCHASE, RETURN\_IN, ADJUSTMENT+)}, \text{Quantity} < 0 \text{ for OUT (SALE, RETURN\_OUT, WRITE\_OFF, ADJUSTMENT-)}$$
* **Assumptions**: Prefetched cache is used in memory when available to eliminate N+1 database queries; database aggregation used as fallback.
* **Example Inputs**: Opening = +10, Sale = -4, Purchase = +14, Sale = -5.
* **Expected Result**: $10 - 4 + 14 - 5 = 15.00$.
* **Actual Tested Result**: `15.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS**.

---

### CALC-010: Stock Asset Valuation
* **Feature Name**: Inventory Asset Valuation (Balance Sheet / Dashboard)
* **Business Definition**: Value of merchandise inventory currently on hand.
* **Source File & Function**: `inventory/models.py:Product.stock_value`, `analytics/services.py`, `analytics/reports_service.py`
* **Source Database Fields**: `inventory_product.current_stock`, `inventory_product.weighted_avg_cost`
* **Formula Currently Used**:
  $$\text{Stock Asset Value} = \max(\text{current\_stock},\; 0.00) \times \text{weighted\_avg\_cost}$$
* **Assumptions**: Negative physical inventory cannot produce negative asset valuation; inventory asset value is strictly bounded at $\ge 0.00$.
* **Example Inputs**: Current Stock = -3 units, Weighted Avg Cost = ₹25.00.
* **Expected Result**: $\max(-3, 0) \times 25.00 = 0.00$.
* **Actual Tested Result**: `0.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_stock_value_with_zero_and_negative_stock`
* **Status**: **PASS** (Defect corrected: floored at 0 to eliminate negative asset balances).

---

### CALC-011: Low-Stock Restocking Deficit
* **Feature Name**: Low-Stock Alert & Reorder Deficit
* **Business Definition**: Units required to restore inventory to the shopkeeper's configured minimum buffer level.
* **Source File & Function**: `inventory/models.py:Product.is_low_stock`, `analytics/services.py`, `analytics/reports_service.py`
* **Source Database Fields**: `inventory_product.current_stock`, `inventory_product.minimum_stock_level`
* **Formula Currently Used**:
  $$\text{Is Low Stock} = (\text{current\_stock} \le \text{minimum\_stock\_level})$$
  $$\text{Restocking Deficit} = \max(\text{minimum\_stock\_level} - \text{current\_stock},\; 0.00)$$
* **Assumptions**: Triggers at or below threshold; handles zero and negative balances.
* **Example Inputs**: Min Stock = 5.00, Current Stock = 2.00.
* **Expected Result**: Is Low Stock = True, Deficit = 3.00.
* **Actual Tested Result**: Is Low Stock = `True`, Deficit = `3.00`.
* **Test Name**: `tests.test_inventory.InventoryModelTests.test_low_stock_detection`
* **Status**: **PASS**.

---

### CALC-012: Cost of Goods Sold (COGS)
* **Feature Name**: Cost of Goods Sold
* **Business Definition**: Total inventory acquisition cost of goods sold during the reporting period, using historical cost at sale time.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `analytics/reports_service.py:get_report_dataset('pnl_summary')`
* **Source Database Fields**: `sales_saleitem.quantity_sold`, `sales_saleitem.historical_cost_per_unit`, `sales_sale.status`
* **Formula Currently Used**:
  $$\text{COGS} = \sum_{\text{confirmed sales}} (\text{quantity\_sold} \times \text{historical\_cost\_per\_unit})$$
* **Assumptions**: Executed via direct database aggregation `Sum(F('quantity_sold') * F('historical_cost_per_unit'))`; voided sales strictly excluded.
* **Example Inputs**: Sale 1: 4 units @ ₹100.00 historical cost; Sale 2: 5 units @ ₹170.00 historical cost.
* **Expected Result**: $(4 \times 100) + (5 \times 170) = 400 + 850 = 1,250.00$.
* **Actual Tested Result**: `1250.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS**.

---

### CALC-013: Gross Profit
* **Feature Name**: Gross Profit
* **Business Definition**: Trading profit earned from sales after deducting the direct cost of goods sold.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `analytics/reports_service.py`
* **Source Database Fields**: `sales_sale.total_amount`, `sales_saleitem.historical_cost_per_unit`
* **Formula Currently Used**:
  $$\text{Gross Profit} = \text{Net Sales Revenue} - \text{COGS}$$
* **Assumptions**: Uses net sales revenue (revenue after customer line-item discounts).
* **Example Inputs**: Net Sales = ₹1,850.00, COGS = ₹1,250.00.
* **Expected Result**: $1,850.00 - 1,250.00 = 600.00$.
* **Actual Tested Result**: `600.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS**.

---

### CALC-014: Gross Profit Margin (%)
* **Feature Name**: Gross Profit Margin Percentage
* **Business Definition**: Percentage of each rupee of sales revenue retained as gross profit.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `analytics/reports_service.py`
* **Source Database Fields**: `gross_profit`, `total_sales_revenue`
* **Formula Currently Used**:
  $$\text{Gross Profit Margin (\%)} = \begin{cases} \left(\frac{\text{Gross Profit}}{\text{Net Sales Revenue}} \times 100\right).\text{round}(2) & \text{if } \text{Net Sales Revenue} > 0 \\ 0.00 & \text{if } \text{Net Sales Revenue} \le 0 \end{cases}$$
* **Assumptions**: Division-by-zero protected; negative margins preserved when sales are sold below cost.
* **Example Inputs**: Gross Profit = ₹600.00, Net Sales = ₹1,850.00.
* **Expected Result**: $\frac{600}{1850} \times 100 = 32.4324...\% \xrightarrow{\text{round}} 32.43\%$.
* **Actual Tested Result**: `32.43%`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS**.

---

### CALC-015: Total Operating Expenses (Accrual)
* **Feature Name**: Operating Expenses
* **Business Definition**: Sum of all operational expenses (rent, electricity, snacks, packaging) incurred during the period.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `expenses/views.py`
* **Source Database Fields**: `expenses_expense.amount`, `expenses_expense.date`
* **Formula Currently Used**:
  $$\text{Total Operating Expenses} = \sum_{\text{in period}} \text{Expense.amount}$$
* **Assumptions**: Accrual accounting basis (total incurred expense regardless of whether paid immediately or pending).
* **Example Inputs**: Rent = ₹500.00 (paid), Electricity = ₹300.00 (unpaid).
* **Expected Result**: $500.00 + 300.00 = 800.00$.
* **Actual Tested Result**: `800.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`
* **Status**: **PASS**.

---

### CALC-016: Expense Outstanding Amount
* **Feature Name**: Expense Payables
* **Business Definition**: Unpaid liability for an operating expense.
* **Source File & Function**: `expenses/models.py:Expense.save`
* **Source Database Fields**: `expenses_expense.amount`, `expenses_expense.amount_paid`
* **Formula Currently Used**:
  $$\text{Outstanding Amount} = \max(\text{amount} - \text{amount\_paid},\; 0.00)$$
* **Assumptions**: Enforced in `Expense.save()`.
* **Example Inputs**: Amount = ₹1,850.00, Paid = ₹1,000.00.
* **Expected Result**: Outstanding = ₹850.00, Status = 'partial'.
* **Actual Tested Result**: `850.00`.
* **Test Name**: `tests.test_expenses.ExpenseModelTests.test_outstanding_amount_calculation`
* **Status**: **PASS**.

---

### CALC-017: Net Operating Profit (Estimate)
* **Feature Name**: Net Operating Profit
* **Business Definition**: Operating profitability of the stationery shop after direct product costs and indirect operating expenses.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `analytics/reports_service.py`
* **Source Database Fields**: `gross_profit`, `total_operating_expenses`
* **Formula Currently Used**:
  $$\text{Net Operating Profit} = \text{Gross Profit} - \text{Total Operating Expenses}$$
* **Assumptions**: Excludes income taxes, loan interest, and capital depreciation (clearly disclosed on UI and reports).
* **Example Inputs**: Gross Profit = ₹400.00, Operating Expenses = ₹800.00.
* **Expected Result**: $400.00 - 800.00 = -400.00$ (Operating Loss of 400).
* **Actual Tested Result**: `-400.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`
* **Status**: **PASS**.

---

### CALC-018: Net Profit Margin (%)
* **Feature Name**: Net Profit Margin Percentage
* **Business Definition**: Percentage of sales revenue remaining as operating profit after all operating expenses.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `analytics/reports_service.py`
* **Source Database Fields**: `net_operating_profit`, `total_sales_revenue`
* **Formula Currently Used**:
  $$\text{Net Profit Margin (\%)} = \begin{cases} \left(\frac{\text{Net Operating Profit}}{\text{Net Sales Revenue}} \times 100\right).\text{round}(2) & \text{if } \text{Net Sales Revenue} > 0 \\ 0.00 & \text{if } \text{Net Sales Revenue} \le 0 \end{cases}$$
* **Assumptions**: Zero division handled; negative margin displayed accurately during periods of net loss.
* **Example Inputs**: Net Profit = -₹400.00, Net Sales = ₹1,000.00.
* **Expected Result**: $\frac{-400}{1000} \times 100 = -40.00\%$.
* **Actual Tested Result**: `-40.00%`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`
* **Status**: **PASS**.

---

### CALC-019: Realized Cash Inflow & Cash Outflow
* **Feature Name**: Cash Flow Analysis
* **Business Definition**: Actual cash liquid movements during the period.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics`
* **Source Database Fields**: `sales_sale.amount_paid`, `purchases_purchase.amount_paid`, `expenses_expense.amount_paid`
* **Formula Currently Used**:
  $$\text{Cash Inflow} = \sum_{\text{confirmed sales}} \text{Sale.amount\_paid}$$
  $$\text{Cash Outflow} = \sum_{\text{confirmed purchases}} \text{Purchase.amount\_paid} + \sum \text{Expense.amount\_paid}$$
* **Assumptions**: Counts cash actually collected and disbursed, contrasting directly with accrual revenue/expenses.
* **Example Inputs**: Sales Paid = ₹600.00, Purchases Paid = ₹800.00, Expenses Paid = ₹500.00.
* **Expected Result**: Cash Inflow = ₹600.00, Cash Outflow = ₹1,300.00.
* **Actual Tested Result**: Inflow = `600.00`, Outflow = `1300.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`
* **Status**: **PASS**.

---

### CALC-020: Net Cash Balance (Period Liquidity)
* **Feature Name**: Period Net Cash Flow
* **Business Definition**: Net liquid change in cash balance during the selected period.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics`
* **Source Database Fields**: `cash_inflow`, `total_cash_outflow`
* **Formula Currently Used**:
  $$\text{Net Cash Flow} = \text{Cash Inflow} - \text{Total Cash Outflow}$$
* **Assumptions**: Can be positive (cash accumulation) or negative (cash deficit/burn).
* **Example Inputs**: Inflow = ₹600.00, Outflow = ₹1,300.00.
* **Expected Result**: $600.00 - 1,300.00 = -700.00$.
* **Actual Tested Result**: `-700.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`
* **Status**: **PASS**.

---

### CALC-021: Average Bill Value
* **Feature Name**: Average Transaction Size (Basket Size)
* **Business Definition**: Average revenue generated per customer bill.
* **Source File & Function**: `analytics/services.py:calculate_financial_metrics` & `analytics/reports_service.py`
* **Source Database Fields**: `sales_sale.total_amount`, `sales_sale.id`
* **Formula Currently Used**:
  $$\text{Avg Bill Value} = \begin{cases} \left(\frac{\text{Total Sales Revenue}}{\text{Bill Count}}\right).\text{round}(2) & \text{if } \text{Bill Count} > 0 \\ 0.00 & \text{if } \text{Bill Count} = 0 \end{cases}$$
* **Assumptions**: Zero division handled.
* **Example Inputs**: Total Sales = ₹1,850.00, Bill Count = 2.
* **Expected Result**: $\frac{1850}{2} = 925.00$.
* **Actual Tested Result**: `925.00`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`
* **Status**: **PASS**.

---

### CALC-022: Sales Growth Rate (%)
* **Feature Name**: Period-Over-Period Sales Growth
* **Business Definition**: Percentage expansion or contraction in sales revenue compared with the previous equivalent period.
* **Source File & Function**: `analytics/services.py:get_comparison_metrics`
* **Source Database Fields**: `curr_metrics['total_sales_revenue']`, `prev_metrics['total_sales_revenue']`
* **Formula Currently Used**:
  $$\text{Sales Growth (\%)} = \begin{cases} \left(\frac{\text{Current Revenue} - \text{Previous Revenue}}{\text{Previous Revenue}} \times 100\right).\text{round}(1) & \text{if } \text{Previous Revenue} > 0 \\ \text{None} & \text{if } \text{Previous Revenue} \le 0 \end{cases}$$
* **Assumptions**: Compares like-for-like MTD days in `this_month` mode; returns `None` if prior revenue is zero.
* **Example Inputs**: Previous Revenue = ₹1,000.00, Current Revenue = ₹1,250.00.
* **Expected Result**: $\frac{1250 - 1000}{1000} \times 100 = +25.0\%$.
* **Actual Tested Result**: `25.0%`.
* **Test Name**: `tests.test_analytics.AnalyticsServiceTests.test_growth_metrics_calculation`
* **Status**: **PASS**.

---

### CALC-023: Profit Growth Rate (%)
* **Feature Name**: Period-Over-Period Profit Growth
* **Business Definition**: Growth in net operating profit, accurately handling transitions from previous losses.
* **Source File & Function**: `analytics/services.py:get_comparison_metrics`
* **Source Database Fields**: `curr_metrics['net_operating_profit']`, `prev_metrics['net_operating_profit']`
* **Formula Currently Used**:
  $$\text{Profit Growth (\%)} = \begin{cases} \left(\frac{\text{Current Profit} - \text{Previous Profit}}{|\text{Previous Profit}|} \times 100\right).\text{round}(1) & \text{if } \text{Previous Profit} \ne 0 \\ \text{None} & \text{if } \text{Previous Profit} = 0 \end{cases}$$
* **Assumptions**: Uses absolute value in denominator ($|\text{Previous Profit}|$) to ensure correct sign and scale when recovering from an operational loss.
* **Example Inputs**: Previous Profit = -₹200.00, Current Profit = +₹300.00.
* **Expected Result**: $\frac{300 - (-200)}{|-200|} \times 100 = \frac{500}{200} \times 100 = +250.0\%$.
* **Actual Tested Result**: `250.0%`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_profit_growth_calculation_with_negative_prior_base`
* **Status**: **PASS** (Defect corrected: prior `if prev_profit > 0` condition discarded negative base cases; now uses absolute denominator).

---

### CALC-024: Low-Stock Estimated Reorder Cost
* **Feature Name**: Restocking Capital Requirement
* **Business Definition**: Estimated capital outlay needed to replenish depleted items to their minimum threshold.
* **Source File & Function**: `analytics/reports_service.py:get_report_dataset('low_stock')`
* **Source Database Fields**: `inventory_product.current_stock`, `inventory_product.minimum_stock_level`, `inventory_product.purchase_cost_per_unit`
* **Formula Currently Used**:
  $$\text{Deficit} = \max(\text{minimum\_stock\_level} - \text{current\_stock},\; 0.00)$$
  $$\text{Estimated Reorder Cost} = \text{Deficit} \times \text{purchase\_cost\_per\_unit}$$
* **Assumptions**: Uses latest purchase cost per unit.
* **Example Inputs**: Deficit = 7 units, Cost = ₹50.00.
* **Expected Result**: $7 \times 50.00 = 350.00$.
* **Actual Tested Result**: `350.00`.
* **Test Name**: `tests.test_audit_edge_cases.AuditEdgeCasesTests.test_low_stock_report_dataset_accuracy`
* **Status**: **PASS**.

---

### CALC-025: Reporting Period & MTD / All-Time Date Bounds
* **Feature Name**: Date Range Selection Engine
* **Business Definition**: Generates date boundaries for financial queries and like-for-like comparison intervals.
* **Source File & Function**: `analytics/services.py:get_date_range`
* **Source Database Fields**: `sales_sale.sale_date`, `purchases_purchase.purchase_date`, `expenses_expense.date`, `inventory_product.stock_entry_date`
* **Formula Currently Used**:
  - `today`: $[T, T]$, comparison $[T-1, T-1]$.
  - `last_7_days`: $[T-6, T]$, comparison $[T-13, T-7]$.
  - `this_month` (MTD): $[M_{\text{start}}, T]$, comparison $[M_{\text{prev\_start}}, \min(T.\text{day}, M_{\text{prev\_days}})]$.
  - `previous_month`: Full prior calendar month.
  - `custom`: $[S, E]$, comparison shifted by exact duration: $[S - D, S - 1]$.
  - `all_time`: $[\min(\text{all transaction dates}), T]$, no comparison.
* **Assumptions**: All models scanned for `all_time` earliest date; MTD compares exact like-for-like day count.
* **Example Inputs**: Today = 20 Oct 2026.
* **Expected Result**: `this_month` = [1 Oct 2026, 20 Oct 2026], comparison = [1 Sept 2026, 20 Sept 2026].
* **Actual Tested Result**: `start: 2026-10-01, end: 2026-10-20, prev_start: 2026-09-01, prev_end: 2026-09-20`.
* **Test Name**: `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_all_time_filter_includes_early_purchases_and_expenses`
* **Status**: **PASS** (Defect corrected: `all_time` scanned all models; MTD made like-for-like).
