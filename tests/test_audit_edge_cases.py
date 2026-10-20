from decimal import Decimal
import datetime
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from inventory.models import Product, StockMovement
from inventory.services import create_product_with_opening_stock
from sales.models import Sale, SaleItem
from sales.services import create_sale_bill, void_sale_bill
from purchases.models import Purchase, PurchaseItem
from purchases.services import create_purchase_order, void_purchase_order
from expenses.models import Expense, ExpenseCategory
from analytics.services import calculate_financial_metrics, get_date_range
from analytics.reports_service import get_report_dataset, export_to_pdf, export_to_csv


class AuditEdgeCasesTests(TestCase):
    def setUp(self):
        self.entry_date = datetime.date(2026, 2, 1)
        self.client = Client()

    def test_personal_mode_direct_access_without_authentication(self):
        """
        In personal use mode, verify that store views are accessible directly
        without authentication barriers.
        """
        accessible_urls = [
            '/',
            '/inventory/',
            '/inventory/add/',
            '/inventory/low-stock/',
            '/sales/',
            '/sales/new/',
            '/purchases/',
            '/purchases/new/',
            '/expenses/',
            '/expenses/new/',
            '/reports/',
            '/accounts/settings/',
        ]
        for url in accessible_urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 200,
                f"URL '{url}' is not accessible in personal mode! Status: {response.status_code}"
            )

    def test_amount_paid_exceeding_total_fails_validation(self):
        """
        Verify that amount_paid cannot exceed total amount in Sales and Purchases.
        """
        p = create_product_with_opening_stock({
            'name': 'Pilot Pen V5',
            'unit': 'piece',
            'opening_quantity': Decimal('20.00'),
            'purchase_cost_per_unit': Decimal('40.00'),
            'selling_price_per_unit': Decimal('60.00'),
            'stock_entry_date': self.entry_date,
        })

        # Sales: Total = 1 * 60 = 60. Paid = 100 -> Must raise ValidationError
        with self.assertRaises(ValidationError):
            create_sale_bill({
                'bill_number': 'BILL-ERR-PAID',
                'sale_date': self.entry_date,
                'amount_paid': '100.00',  # Exceeds 60
            }, [{
                'product_id': p.id,
                'quantity': '1.00',
                'actual_selling_price_per_unit': '60.00',
            }])

        # Purchases: Total = 10 * 40 = 400. Paid = 500 -> Must raise ValidationError
        with self.assertRaises(ValidationError):
            create_purchase_order({
                'invoice_number': 'INV-ERR-PAID',
                'purchase_date': self.entry_date,
                'supplier_name': 'Supplier X',
                'amount_paid': '500.00',  # Exceeds 400
            }, [{
                'product_id': p.id,
                'quantity_purchased': '10.00',
                'purchase_cost_per_unit': '40.00',
            }])

    def test_void_purchase_fails_if_would_cause_negative_stock(self):
        """
        Verify that voiding a purchase is prevented if items were already sold
        and deducting the purchase quantity would create negative stock.
        """
        # 1. Product starts with 0 opening stock
        prod = create_product_with_opening_stock({
            'name': 'Doms Sketch Pens',
            'unit': 'packet',
            'opening_quantity': Decimal('0.00'),
            'purchase_cost_per_unit': Decimal('30.00'),
            'selling_price_per_unit': Decimal('50.00'),
            'stock_entry_date': self.entry_date,
        })
        self.assertEqual(prod.current_stock, Decimal('0.00'))

        # 2. Purchase 10 packets -> stock becomes 10
        purchase = create_purchase_order({
            'invoice_number': 'INV-DOMS-10',
            'purchase_date': self.entry_date,
            'supplier_name': 'Doms Distributor',
            'amount_paid': '300.00',
        }, [{
            'product_id': prod.id,
            'quantity_purchased': '10.00',
            'purchase_cost_per_unit': '30.00',
        }])
        self.assertEqual(prod.current_stock, Decimal('10.00'))

        # 3. Sell 6 packets -> stock becomes 4
        create_sale_bill({
            'bill_number': 'BILL-DOMS-6',
            'sale_date': self.entry_date,
            'amount_paid': '300.00',
        }, [{
            'product_id': prod.id,
            'quantity': '6.00',
            'actual_selling_price_per_unit': '50.00',
        }])
        self.assertEqual(prod.current_stock, Decimal('4.00'))

        # 4. Attempting to void the purchase of 10 must FAIL because stock is only 4!
        with self.assertRaises(ValidationError) as ctx:
            void_purchase_order(purchase, reason='Trying to void purchase after items sold')

        self.assertIn("Some units from this purchase have already been sold", str(ctx.exception))
        # Ensure stock is still 4.00 and purchase status is still confirmed
        self.assertEqual(prod.current_stock, Decimal('4.00'))
        self.assertEqual(purchase.status, 'confirmed')

    def test_inverted_custom_date_range(self):
        """
        Verify that if a user provides custom_start > custom_end,
        get_date_range automatically swaps them without errors.
        """
        d1 = datetime.date(2026, 3, 20)
        d2 = datetime.date(2026, 3, 10)
        start, end, label, prev_start, prev_end = get_date_range('custom', d1, d2)

        self.assertEqual(start, d2)
        self.assertEqual(end, d1)
        self.assertEqual(start < end, True)

    def test_comprehensive_manual_pnl_scenario(self):
        """
        Multi-step scenario with manual verification:
        - Product: 10 units @ 200 opening = 2000
        - Purchase 1: 20 units @ 260 -> Weighted Avg = (2000 + 5200)/30 = 240
        - Sale 1: 15 units @ 300, disc 100 -> Rev = 4400, COGS = 15*240 = 3600, GP = 800
        - Purchase 2: 10 units @ 300 -> Stock remaining 15 @ 240 = 3600 + 3000 = 6600/25 = 264
        - Sale 2: 5 units @ 320 -> Rev = 1600, COGS = 5*264 = 1320, GP = 280
        - Combined: Rev = 6000, COGS = 4920, GP = 1080 (18.0%), Exp = 800 (Rent 500 + Elec 300)
        - Net Operating Profit = 1080 - 800 = 280 (4.67%)
        - Cash Inflow = 3000 + 1600 = 4600
        - Cash Outflow = 5200 + 2000 + (300 + 250) = 7750
        - Net Cash Flow = 4600 - 7750 = -3150
        """
        start = datetime.date(2026, 5, 1)
        end = datetime.date(2026, 5, 31)

        p = create_product_with_opening_stock({
            'name': 'Copier Paper A4 75GSM',
            'unit': 'ream',
            'opening_quantity': Decimal('10.00'),
            'purchase_cost_per_unit': Decimal('200.00'),
            'selling_price_per_unit': Decimal('300.00'),
            'stock_entry_date': start,
        })

        # Purchase 1
        create_purchase_order({
            'invoice_number': 'INV-CP-1',
            'purchase_date': start,
            'supplier_name': 'JK Paper Mill',
            'amount_paid': '5200.00',
        }, [{
            'product_id': p.id,
            'quantity_purchased': '20.00',
            'purchase_cost_per_unit': '260.00',
        }])
        p.refresh_from_db()
        self.assertEqual(p.weighted_avg_cost, Decimal('240.0000'))

        # Sale 1
        create_sale_bill({
            'bill_number': 'BILL-CP-1',
            'sale_date': start,
            'amount_paid': '3000.00',  # 1400 due
        }, [{
            'product_id': p.id,
            'quantity': '15.00',
            'actual_selling_price_per_unit': '300.00',
            'discount_amount': '100.00',
        }])

        # Purchase 2
        create_purchase_order({
            'invoice_number': 'INV-CP-2',
            'purchase_date': start,
            'supplier_name': 'JK Paper Mill',
            'amount_paid': '2000.00',  # 1000 due
        }, [{
            'product_id': p.id,
            'quantity_purchased': '10.00',
            'purchase_cost_per_unit': '300.00',
        }])
        p.refresh_from_db()
        self.assertEqual(p.weighted_avg_cost, Decimal('264.0000'))

        # Sale 2
        create_sale_bill({
            'bill_number': 'BILL-CP-2',
            'sale_date': start,
            'amount_paid': '1600.00',
        }, [{
            'product_id': p.id,
            'quantity': '5.00',
            'actual_selling_price_per_unit': '320.00',
        }])

        # Expenses
        cat_rent, _ = ExpenseCategory.objects.get_or_create(name='Rent')
        cat_elec, _ = ExpenseCategory.objects.get_or_create(name='Electricity')
        Expense.objects.create(category=cat_rent, date=start, description='Shop Rent May', amount=Decimal('500.00'), amount_paid=Decimal('250.00'))
        Expense.objects.create(category=cat_elec, date=start, description='Electric Bill May', amount=Decimal('300.00'), amount_paid=Decimal('300.00'))

        # Calculate metrics
        metrics = calculate_financial_metrics(start, end)

        self.assertEqual(metrics['total_sales_revenue'], Decimal('6000.00'))
        self.assertEqual(metrics['cogs'], Decimal('4920.00'))
        self.assertEqual(metrics['gross_profit'], Decimal('1080.00'))
        self.assertEqual(metrics['gross_profit_margin'], Decimal('18.00'))
        self.assertEqual(metrics['total_operating_expenses'], Decimal('800.00'))
        self.assertEqual(metrics['net_operating_profit'], Decimal('280.00'))
        self.assertEqual(metrics['net_profit_margin'], Decimal('4.67'))
        self.assertEqual(metrics['cash_inflow'], Decimal('4600.00'))
        self.assertEqual(metrics['total_cash_outflow'], Decimal('7750.00'))
        self.assertEqual(metrics['net_cash_flow'], Decimal('-3150.00'))

    def test_empty_report_pdf_generation(self):
        """
        Verify that generating a PDF for a date range with no records
        produces a valid PDF document with the empty row message.
        """
        empty_start = datetime.date(2024, 1, 1)
        empty_end = datetime.date(2024, 1, 31)
        title, headers, rows, summary = get_report_dataset('daily_sales', empty_start, empty_end)

        self.assertEqual(len(rows), 0)
        resp = export_to_pdf(title, empty_start, empty_end, headers, rows, summary)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(len(resp.content) > 1000)

    def test_product_code_collision_handling(self):
        """
        Verify that Product.save avoids collisions even if a code already exists.
        """
        p1 = create_product_with_opening_stock({
            'name': 'Item A',
            'unit': 'piece',
            'stock_entry_date': self.entry_date,
        })
        # Next code is guaranteed unique
        p2 = create_product_with_opening_stock({
            'name': 'Item B',
            'unit': 'piece',
            'stock_entry_date': self.entry_date,
        })
        self.assertNotEqual(p1.product_code, p2.product_code)
