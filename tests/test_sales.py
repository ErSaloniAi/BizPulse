from decimal import Decimal
import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from inventory.models import Product
from inventory.services import create_product_with_opening_stock
from sales.models import Sale, SaleItem
from sales.services import create_sale_bill, void_sale_bill, generate_next_bill_number


class SalesTests(TestCase):
    def setUp(self):
        self.entry_date = datetime.date(2026, 1, 1)
        self.p1 = create_product_with_opening_stock({
            'name': 'Classmate Notebook',
            'unit': 'piece',
            'opening_quantity': Decimal('50.00'),
            'purchase_cost_per_unit': Decimal('40.00'),
            'selling_price_per_unit': Decimal('60.00'),
            'stock_entry_date': self.entry_date,
        })
        self.p2 = create_product_with_opening_stock({
            'name': 'Reynolds 045 Pen',
            'unit': 'piece',
            'opening_quantity': Decimal('100.00'),
            'purchase_cost_per_unit': Decimal('7.00'),
            'selling_price_per_unit': Decimal('10.00'),
            'stock_entry_date': self.entry_date,
        })

    def test_create_sale_bill_success(self):
        sale_data = {
            'bill_number': 'BILL-0001',
            'sale_date': self.entry_date,
            'customer_name': 'M/s National Coaching',
            'amount_paid': '700.00',
            'payment_method': 'cash',
        }
        items_data = [
            {
                'product_id': self.p1.id,
                'quantity': '10.00',
                'actual_selling_price_per_unit': '60.00',
                'discount_amount': '0.00',
            },
            {
                'product_id': self.p2.id,
                'quantity': '20.00',
                'actual_selling_price_per_unit': '10.00',
                'discount_amount': '50.00',  # 20 * 10 - 50 = 150
            }
        ]
        # Total expected: (10*60) + (20*10 - 50) = 600 + 150 = 750
        sale = create_sale_bill(sale_data, items_data)

        self.assertEqual(sale.total_amount, Decimal('750.00'))
        self.assertEqual(sale.amount_paid, Decimal('700.00'))
        self.assertEqual(sale.outstanding_amount, Decimal('50.00'))
        self.assertEqual(sale.payment_status, 'partial')

        # Check stock deduction
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.current_stock, Decimal('40.00'))
        self.assertEqual(self.p2.current_stock, Decimal('80.00'))

        # Check historical cost capture
        item1 = sale.items.get(product=self.p1)
        self.assertEqual(item1.historical_cost_per_unit, Decimal('40.00'))

    def test_prevent_negative_stock(self):
        sale_data = {
            'bill_number': 'BILL-0002',
            'sale_date': self.entry_date,
            'amount_paid': '0.00',
        }
        items_data = [
            {
                'product_id': self.p1.id,
                'quantity': '60.00',  # Only 50 in stock!
                'actual_selling_price_per_unit': '60.00',
            }
        ]
        with self.assertRaises(ValidationError):
            create_sale_bill(sale_data, items_data)

        # Confirm stock was NOT changed
        self.assertEqual(self.p1.current_stock, Decimal('50.00'))

    def test_prevent_duplicate_bill_number(self):
        sale_data = {
            'bill_number': 'BILL-0001',
            'sale_date': self.entry_date,
            'amount_paid': '60.00',
        }
        items_data = [{
            'product_id': self.p1.id,
            'quantity': '1.00',
            'actual_selling_price_per_unit': '60.00',
        }]
        create_sale_bill(sale_data, items_data)

        # Attempt to create bill with identical bill number
        with self.assertRaises(ValidationError):
            create_sale_bill(sale_data, items_data)

    def test_historical_cost_stability(self):
        """
        Verify that past sales profit calculations remain unchanged
        even if product current purchase cost or selling price changes later.
        """
        sale = create_sale_bill({
            'bill_number': 'BILL-HIST-1',
            'sale_date': self.entry_date,
            'amount_paid': '120.00',
        }, [{
            'product_id': self.p1.id,
            'quantity': '2.00',
            'actual_selling_price_per_unit': '60.00',
        }])

        item = sale.items.first()
        initial_cogs = item.quantity_sold * item.historical_cost_per_unit
        self.assertEqual(initial_cogs, Decimal('80.00'))

        # Later, owner changes product price and cost
        self.p1.purchase_cost_per_unit = Decimal('55.00')
        self.p1.selling_price_per_unit = Decimal('75.00')
        self.p1.save()

        # Reload sale item from db
        item.refresh_from_db()
        cogs_after = item.quantity_sold * item.historical_cost_per_unit
        self.assertEqual(cogs_after, Decimal('80.00'))  # Must NOT change!

    def test_void_bill_restores_stock(self):
        sale = create_sale_bill({
            'bill_number': 'BILL-VOID-1',
            'sale_date': self.entry_date,
            'amount_paid': '60.00',
        }, [{
            'product_id': self.p1.id,
            'quantity': '5.00',
            'actual_selling_price_per_unit': '60.00',
        }])
        self.assertEqual(self.p1.current_stock, Decimal('45.00'))

        void_sale_bill(sale, reason='Customer returned goods')
        self.assertEqual(sale.status, 'voided')
        self.assertEqual(self.p1.current_stock, Decimal('50.00'))  # Stock restored!
