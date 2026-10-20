# BizPulse: Formula, Calculation & Data Logic Defect Catalog

## Overview

During the comprehensive financial and mathematical audit of **BizPulse**, 10 distinct defects were discovered in calculation algorithms, inventory costing methods, model invariants, database aggregation, and date range logic.

Every identified defect was investigated to its root cause, corrected with robust production-grade code, and validated against reproducible test cases in the test suite.

---

## Defect Summary Table

| Defect ID | Severity | Module / Location | Defect Title | Impact | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **DEF-001** | **Medium** | `sales/services.py`<br>`purchases/services.py` | Subtotal Quantization Mismatch | Fractional cent discrepancies in bill totals | **RESOLVED** |
| **DEF-002** | **High** | `sales/models.py`<br>`purchases/models.py` | Model-Level Invariant Enforcement Missing | Out-of-sync dues when updating `amount_paid` | **RESOLVED** |
| **DEF-003** | **Critical** | `purchases/services.py:void_purchase_order` | Purchase Void Cost Reversal Missing | Permanent distortion of inventory valuation & COGS | **RESOLVED** |
| **DEF-004** | **Medium** | `inventory/csv_services.py` | CSV Bulk Import Moving Average Recalculation | Outdated weighted average cost after CSV batch stock additions | **RESOLVED** |
| **DEF-005** | **Low** | `inventory/models.py`<br>`analytics/services.py` | Negative Stock Asset Valuation Floor Missing | Negative asset valuation on balance sheet / dashboard | **RESOLVED** |
| **DEF-006** | **Low** | `inventory/models.py:Product.current_stock` | N+1 Query on Prefetched Stock Movements | High database query overhead on product listing pages | **RESOLVED** |
| **DEF-007** | **Medium** | `analytics/services.py`<br>`analytics/reports_service.py` | Python In-Memory COGS Aggregation | Inefficient memory consumption on large sales datasets | **RESOLVED** |
| **DEF-008** | **Medium** | `analytics/services.py:get_date_range` | All-Time Filter Early Transaction Blindspot | Early purchases/expenses before first sale omitted from all-time | **RESOLVED** |
| **DEF-009** | **High** | `analytics/services.py:get_date_range` | MTD Comparison Period Asymmetry | Inaccurate negative growth rates comparing partial month to full month | **RESOLVED** |
| **DEF-010** | **Medium** | `analytics/services.py:get_comparison_metrics` | Profit Growth Calculation Discarding Negative Base | Failure to report profit growth when transitioning from a prior net loss | **RESOLVED** |

---

## Detailed Defect Reports

### DEF-001: Subtotal Quantization Mismatch in Bill Creation Services

* **Component**: `sales/services.py:create_sale_bill`, `purchases/services.py:create_purchase_order`
* **Severity**: Medium
* **Root Cause**:
  In `create_sale_bill`, the line item net total was calculated as `(qty * unit_price) - disc` without immediate `.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`. While the model's `SaleItem.line_total` field saved as `Decimal(12, 2)`, the in-memory running total accumulated unquantized floating values. When line items with fractional rates or quantities were entered (e.g. 1.25 kg @ ₹12.33), the sum of in-memory decimals could differ by ₹0.01 from the sum of stored line items.
* **Mathematical Flaw**:
  $$\text{Total}_{\text{in-memory}} = \sum_{i=1}^{n} \text{raw\_subtotal}_i \ne \sum_{i=1}^{n} \text{round}(\text{raw\_subtotal}_i, 2)$$
* **Applied Code Fix**:
  ```python
  # sales/services.py & purchases/services.py
  line_total = max(
      Decimal("0.00"),
      (Decimal(str(qty)) * Decimal(str(price))) - Decimal(str(disc))
  ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
  ```
* **Verification Proof**:
  Verified by `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_line_total_quantization_and_rounding`. Tested with 1.25 units @ ₹12.33 less ₹1.00 discount; produces exact ₹14.41 line total and invoice grand total.

---

### DEF-002: Model-Level Outstanding Amount & Status Invariant Enforcement

* **Component**: `sales/models.py:Sale`, `purchases/models.py:Purchase`
* **Severity**: High
* **Root Cause**:
  The `Expense` model had a dedicated `save()` override that computed `outstanding_amount = max(amount - amount_paid, Decimal('0.00'))` and set `status = 'paid' | 'partial' | 'unpaid'`. However, `Sale` and `Purchase` models did not have this override; their calculation was performed only in service helper functions. If a user or admin updated `amount_paid` directly on the model or via Django Admin, `outstanding_amount` remained unchanged, violating the fundamental accounting invariant $\text{Total} = \text{Paid} + \text{Outstanding}$.
* **Applied Code Fix**:
  ```python
  # sales/models.py & purchases/models.py
  def save(self, *args, **kwargs):
      if self.total_amount is not None:
          if self.amount_paid is None:
              self.amount_paid = Decimal("0.00")
          self.outstanding_amount = max(Decimal("0.00"), self.total_amount - self.amount_paid)
          if self.total_amount == Decimal("0.00") or self.amount_paid >= self.total_amount:
              self.payment_status = "paid"
          elif self.amount_paid > Decimal("0.00"):
              self.payment_status = "partial"
          else:
              self.payment_status = "unpaid"
      super().save(*args, **kwargs)
  ```
* **Verification Proof**:
  Verified by `tests.test_audit_edge_cases.AuditEdgeCasesTests.test_partial_payment_and_outstanding_balance_reconciliation` and `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_accrual_profit_vs_cash_flow_reconciliation`.

---

### DEF-003: Purchase Voiding Weighted-Average Cost Reversal

* **Component**: `purchases/services.py:void_purchase_order`
* **Severity**: Critical
* **Root Cause**:
  When a purchase order was voided, the system created a compensatory `RETURN_OUT` stock movement to restore the physical unit count. However, it completely neglected to revert the product's `weighted_avg_cost`.
  If an erroneous purchase of 100 units @ ₹500 was entered for a product that previously cost ₹50, the average cost skyrocketed. When voided, stock was removed, but the average cost stayed elevated at ~₹450. Subsequent sales would record massively inflated historical COGS, resulting in false operating losses.
* **Mathematical Flaw**:
  $$\text{Post-Void Cost} = \text{Pre-Void Cost} \quad (\text{Permanent valuation contamination})$$
* **Applied Code Fix**:
  ```python
  # purchases/services.py:void_purchase_order
  remaining_stock = current_stock - item.quantity_purchased
  if remaining_stock > 0:
      restored_total_val = (current_stock * product.weighted_avg_cost) - (item.quantity_purchased * item.purchase_cost_per_unit)
      restored_cost = (restored_total_val / remaining_stock).quantize(Decimal("0.0001"))
      product.weighted_avg_cost = max(Decimal("0.0000"), restored_cost)
  else:
      product.weighted_avg_cost = item.purchase_cost_per_unit
  product.save(update_fields=["weighted_avg_cost", "updated_at"])
  ```
* **Verification Proof**:
  Verified by `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_purchase_voiding_restores_prior_weighted_avg_cost`. Verified that 20 units @ ₹100 voiding 10 units @ ₹150 accurately restores remaining 10 units to ₹50.0000 average cost.

---

### DEF-004: CSV Bulk Product Import Weighted-Average Recalculation

* **Component**: `inventory/csv_services.py:import_products_from_csv`
* **Severity**: Medium
* **Root Cause**:
  When re-importing products via CSV where a product already existed in the database, the import added new stock movements but set `product.purchase_cost_per_unit = new_cost` without recalculating `weighted_avg_cost`. This created an inconsistency between web-based purchase orders (which calculated moving averages) and CSV batch imports.
* **Applied Code Fix**:
  ```python
  # inventory/csv_services.py
  if current_stock > 0 and stock_val > 0:
      total_val = (current_stock * product.weighted_avg_cost) + (stock_val * purchase_cost)
      new_avg = (total_val / (current_stock + stock_val)).quantize(Decimal("0.0001"))
      product.weighted_avg_cost = new_avg
  elif stock_val > 0:
      product.weighted_avg_cost = purchase_cost
  ```
* **Verification Proof**:
  Verified by running `tests.test_csv_uploads.CSVUploadTests` and validating consistency between CSV imports and manual purchase orders.

---

### DEF-005: Negative Stock Asset Valuation Floor

* **Component**: `inventory/models.py:Product.stock_value`, `analytics/services.py`, `analytics/reports_service.py`
* **Severity**: Low
* **Root Cause**:
  If a shopkeeper recorded sales before entering opening stock, physical stock temporarily showed a negative value (e.g. -5 pens). While the negative stock count is an accurate physical deficit flag, multiplying negative units by weighted average cost produced a negative asset value (e.g. -₹125.00) in balance sheet and inventory valuation cards. Under accounting standards, an asset cannot have a negative balance (it represents a deficit, not a negative asset).
* **Mathematical Flaw**:
  $$\text{Asset Value} = \text{current\_stock} \times \text{weighted\_avg\_cost} < 0.00 \quad (\text{Invalid Balance Sheet Asset})$$
* **Applied Code Fix**:
  ```python
  # inventory/models.py
  @property
  def stock_value(self):
      stock = self.current_stock
      if stock <= Decimal("0.00"):
          return Decimal("0.00")
      return (stock * self.weighted_avg_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
  ```
* **Verification Proof**:
  Verified by `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_stock_value_with_zero_and_negative_stock`. Returns ₹0.00 for 0 units and -3 units.

---

### DEF-006: N+1 Query on Prefetched Stock Movements

* **Component**: `inventory/models.py:Product.current_stock`
* **Severity**: Low (Performance & Scalability)
* **Root Cause**:
  `Product.current_stock` executed `self.stock_movements.aggregate(total=Sum('quantity'))['total']`. In Django ORM, `.aggregate()` always executes a new SQL query against the database, completely ignoring `prefetch_related('stock_movements')`. On views listing 100 products, this triggered 100 separate database queries.
* **Applied Code Fix**:
  ```python
  # inventory/models.py
  @property
  def current_stock(self):
      if hasattr(self, '_prefetched_objects_cache') and 'stock_movements' in self._prefetched_objects_cache:
          total = sum(m.quantity for m in self.stock_movements.all())
          return Decimal(str(total or 0)).quantize(Decimal("0.01"))
      res = self.stock_movements.aggregate(total=models.Sum('quantity'))['total']
      return res or Decimal('0.00')
  ```
* **Verification Proof**:
  Verified via inventory views and test suite execution; zero regression, eliminates database query amplification.

---

### DEF-007: Python In-Memory COGS Aggregation

* **Component**: `analytics/services.py:calculate_financial_metrics`, `analytics/reports_service.py`
* **Severity**: Medium (Performance & Scalability)
* **Root Cause**:
  COGS was computed by fetching all `SaleItem` records across the date range into a Python list and summing `item.quantity_sold * item.historical_cost_per_unit` in a Python loop. Over hundreds of bills and thousands of line items, this loads significant data into web server memory.
* **Applied Code Fix**:
  ```python
  # analytics/services.py & analytics/reports_service.py
  cogs_agg = SaleItem.objects.filter(
      sale__status=Sale.STATUS_CONFIRMED,
      sale__sale_date__gte=start_date,
      sale__sale_date__lte=end_date,
  ).aggregate(
      total_cogs=Sum(F('quantity_sold') * F('historical_cost_per_unit'), output_field=DecimalField(max_digits=12, decimal_places=2))
  )
  cogs = (cogs_agg['total_cogs'] or Decimal('0.00')).quantize(Decimal('0.01'))
  ```
* **Verification Proof**:
  Directly executed in PostgreSQL via `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_weighted_average_cost_and_historical_cogs_preservation`.

---

### DEF-008: All-Time Filter Early Transaction Blindspot

* **Component**: `analytics/services.py:get_date_range`
* **Severity**: Medium
* **Root Cause**:
  The `all_time` date range preset initialized `start_date` by querying only `Sale.objects.earliest('sale_date')`. In a newly opened business, inventory purchases, store fit-out expenses, and opening stock entries precede the first customer sale. Omitting these dates from the all-time range caused startup expenses and opening purchases to vanish from all-time reports.
* **Applied Code Fix**:
  ```python
  # analytics/services.py:get_date_range
  earliest_dates = []
  if Sale.objects.filter(status=Sale.STATUS_CONFIRMED).exists():
      earliest_dates.append(Sale.objects.filter(status=Sale.STATUS_CONFIRMED).aggregate(Min('sale_date'))['sale_date__min'])
  if Purchase.objects.filter(status=Purchase.STATUS_CONFIRMED).exists():
      earliest_dates.append(Purchase.objects.filter(status=Purchase.STATUS_CONFIRMED).aggregate(Min('purchase_date'))['purchase_date__min'])
  if Expense.objects.exists():
      earliest_dates.append(Expense.objects.aggregate(Min('date'))['date__min'])
  if Product.objects.exists():
      earliest_dates.append(Product.objects.aggregate(Min('stock_entry_date'))['stock_entry_date__min'])
  earliest = min([d for d in earliest_dates if d]) if earliest_dates else today
  ```
* **Verification Proof**:
  Verified by `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_all_time_filter_includes_early_purchases_and_expenses`.

---

### DEF-009: Month-to-Date (MTD) Like-for-Like Comparison Asymmetry

* **Component**: `analytics/services.py:get_date_range`
* **Severity**: High
* **Root Cause**:
  When viewing `this_month` on the 10th of the month, the current period was [Oct 1 to Oct 10] (10 days). However, the comparison period was configured as [Sept 1 to Sept 30] (30 days). Comparing 10 days of sales to 30 days of sales generated misleading negative growth rates (e.g. -65% revenue collapse) on the dashboard KPI cards, causing shopkeeper panic.
* **Applied Code Fix**:
  ```python
  # analytics/services.py:get_date_range
  # For 'this_month':
  first_day_prev_month = (first_day_curr_month - timedelta(days=1)).replace(day=1)
  last_day_prev_month = first_day_curr_month - timedelta(days=1)
  prev_end_day = min(today.day, last_day_prev_month.day)
  prev_start = first_day_prev_month
  prev_end = first_day_prev_month.replace(day=prev_end_day)
  ```
* **Verification Proof**:
  Verified in test suite; `this_month` on 20th Oct compares exactly against 1st Sept to 20th Sept (20 days vs 20 days).

---

### DEF-010: Profit Growth Rate on Negative Prior Base

* **Component**: `analytics/services.py:get_comparison_metrics`
* **Severity**: Medium
* **Root Cause**:
  The previous growth calculation used `if prev_profit > 0:`. If a shop had an operating loss of ₹200 last month and earned an operating profit of ₹300 this month, the system evaluated `prev_profit > 0` as False and returned `None`, hiding the financial recovery. Furthermore, naive percentage formulas dividing by a negative number reverse the growth sign: $(300 - (-200)) / (-200) = 500 / -200 = -250\%$, which falsely presents profit growth as a massive loss!
* **Mathematical Flaw**:
  $$\text{Standard Growth} = \frac{P_{\text{curr}} - P_{\text{prev}}}{P_{\text{prev}}} \implies \frac{300 - (-200)}{-200} = -250\% \quad (\text{Mathematically Invalid Sign})$$
* **Applied Code Fix**:
  ```python
  # analytics/services.py:get_comparison_metrics
  if prev_profit != Decimal("0.00"):
      profit_growth = (((curr_profit - prev_profit) / abs(prev_profit)) * 100).quantize(
          Decimal("0.1"), rounding=ROUND_HALF_UP
      )
  else:
      profit_growth = None
  ```
* **Verification Proof**:
  Verified by `tests.test_financial_audit_oracle.FinancialAuditOracleTests.test_profit_growth_calculation_with_negative_prior_base`. Correctly outputs `+250.0%`.
