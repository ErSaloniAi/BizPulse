from decimal import Decimal
import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from inventory.models import Product
from inventory.services import create_product_with_opening_stock
from sales.services import create_sale_bill
from purchases.services import create_purchase_order
from expenses.models import Expense, ExpenseCategory
from analytics.services import calculate_financial_metrics, get_date_range
from analytics.reports_service import get_report_dataset, export_to_csv, export_to_pdf


class AnalyticsAndReportsTests(TestCase):
    def setUp(self):
        self.entry_date = datetime.date(2026, 1, 15)
        self.start_date = datetime.date(2026, 1, 1)
        self.end_date = datetime.date(2026, 1, 31)

        # 1. Product setup: 100 units at ₹50 cost, sells at ₹80
        self.p1 = create_product_with_opening_stock({
            'name': 'Register 200 Pages',
            'unit': 'piece',
            'opening_quantity': Decimal('100.00'),
            'purchase_cost_per_unit': Decimal('50.00'),
            'selling_price_per_unit': Decimal('80.00'),
            'stock_entry_date': self.entry_date,
        })

        # 2. Sale: sell 20 units at ₹80 = ₹1600 revenue. COGS = 20 * 50 = ₹1000. Gross Profit = ₹600.
        self.sale = create_sale_bill({
            'bill_number': 'BILL-TEST-01',
            'sale_date': self.entry_date,
            'amount_paid': '1200.00',  # 400 due
        }, [{
            'product_id': self.p1.id,
            'quantity': '20.00',
            'actual_selling_price_per_unit': '80.00',
        }])

        # 3. Operating Expense: Rent ₹200
        cat, _ = ExpenseCategory.objects.get_or_create(name='Rent')
        self.exp = Expense.objects.create(
            category=cat,
            date=self.entry_date,
            description='Shop Space Rent',
            amount=Decimal('200.00'),
            amount_paid=Decimal('200.00'),
        )

        # 4. Stock Purchase: Buy 10 units at ₹50 = ₹500 (Inventory Asset, NOT Operating Expense!)
        self.purch = create_purchase_order({
            'invoice_number': 'INV-STOCK-1',
            'purchase_date': self.entry_date,
            'supplier_name': 'Paper Mill',
            'amount_paid': '500.00',
        }, [{
            'product_id': self.p1.id,
            'quantity_purchased': '10.00',
            'purchase_cost_per_unit': '50.00',
        }])

    def test_pnl_calculations(self):
        metrics = calculate_financial_metrics(self.start_date, self.end_date)

        # Sales Revenue: ₹1600.00
        self.assertEqual(metrics['total_sales_revenue'], Decimal('1600.00'))

        # COGS: 20 units * ₹50 = ₹1000.00
        self.assertEqual(metrics['cogs'], Decimal('1000.00'))

        # Gross Profit: 1600 - 1000 = ₹600.00
        self.assertEqual(metrics['gross_profit'], Decimal('600.00'))

        # Gross Profit Margin: 600 / 1600 * 100 = 37.5%
        self.assertEqual(metrics['gross_profit_margin'], Decimal('37.50'))

        # Operating Expenses: ₹200.00 (Purchases of ₹500 are NOT counted as operating expense!)
        self.assertEqual(metrics['total_operating_expenses'], Decimal('200.00'))

        # Net Operating Profit: Gross Profit (600) - Operating Expenses (200) = ₹400.00
        self.assertEqual(metrics['net_operating_profit'], Decimal('400.00'))

        # Net Profit Margin: 400 / 1600 * 100 = 25.0%
        self.assertEqual(metrics['net_profit_margin'], Decimal('25.00'))

        # Cash Inflow: ₹1200.00
        self.assertEqual(metrics['cash_inflow'], Decimal('1200.00'))

        # Cash Outflow: Purchases (500) + Expenses (200) = ₹700.00
        self.assertEqual(metrics['total_cash_outflow'], Decimal('700.00'))

        # Net Cash Flow: 1200 - 700 = ₹500.00 (Notice Net Profit is 400, while Cash Flow is 500!)
        self.assertEqual(metrics['net_cash_flow'], Decimal('500.00'))

    def test_zero_sales_safe_division(self):
        # Period with no sales
        empty_start = datetime.date(2025, 1, 1)
        empty_end = datetime.date(2025, 1, 31)

        metrics = calculate_financial_metrics(empty_start, empty_end)
        self.assertEqual(metrics['total_sales_revenue'], Decimal('0.00'))
        self.assertEqual(metrics['gross_profit_margin'], Decimal('0.00'))
        self.assertEqual(metrics['net_profit_margin'], Decimal('0.00'))
        self.assertEqual(metrics['avg_bill_value'], Decimal('0.00'))

    def test_reports_dataset_generation(self):
        reports = ['daily_sales', 'monthly_sales', 'pnl_summary', 'product_sales', 'expense_category', 'purchases', 'stock', 'low_stock']
        for r_type in reports:
            title, headers, rows, summary = get_report_dataset(r_type, self.start_date, self.end_date)
            self.assertIsNotNone(title)
            self.assertTrue(len(headers) > 0)

    def test_csv_export(self):
        title, headers, rows, summary = get_report_dataset('daily_sales', self.start_date, self.end_date)
        response = export_to_csv(title, self.start_date, self.end_date, headers, rows, summary)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue('daily_sales' in response['Content-Disposition'])

    def test_pdf_export(self):
        title, headers, rows, summary = get_report_dataset('pnl_summary', self.start_date, self.end_date)
        response = export_to_pdf(title, self.start_date, self.end_date, headers, rows, summary)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)
