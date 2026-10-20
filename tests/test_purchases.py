from decimal import Decimal
import datetime
from django.test import TestCase
from inventory.models import Product
from inventory.services import create_product_with_opening_stock
from purchases.models import Purchase, PurchaseItem
from purchases.services import create_purchase_order, void_purchase_order


class PurchasesTests(TestCase):
    def setUp(self):
        self.entry_date = datetime.date(2026, 1, 1)
        # 10 units at ₹40 = ₹400
        self.p1 = create_product_with_opening_stock({
            'name': 'Fevicol MR 100g',
            'unit': 'piece',
            'opening_quantity': Decimal('10.00'),
            'purchase_cost_per_unit': Decimal('40.00'),
            'selling_price_per_unit': Decimal('55.00'),
            'stock_entry_date': self.entry_date,
        })

    def test_create_purchase_order_and_weighted_average(self):
        # Buy 10 more units at ₹50 = ₹500
        # Total units = 20
        # Total cost = (10*40) + (10*50) = 400 + 500 = 900
        # New weighted average cost = 900 / 20 = ₹45.00
        purchase_data = {
            'invoice_number': 'INV-PIDILITE-101',
            'purchase_date': self.entry_date,
            'supplier_name': 'Pidilite Distributor',
            'amount_paid': '300.00',
        }
        items_data = [
            {
                'product_id': self.p1.id,
                'quantity_purchased': '10.00',
                'purchase_cost_per_unit': '50.00',
            }
        ]
        purchase = create_purchase_order(purchase_data, items_data)

        self.assertEqual(purchase.total_amount, Decimal('500.00'))
        self.assertEqual(purchase.amount_paid, Decimal('300.00'))
        self.assertEqual(purchase.outstanding_amount, Decimal('200.00'))
        self.assertEqual(purchase.payment_status, 'partial')

        # Check stock incremented
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.current_stock, Decimal('20.00'))

        # Check weighted-average cost updated
        self.assertEqual(self.p1.weighted_avg_cost, Decimal('45.0000'))
        self.assertEqual(self.p1.purchase_cost_per_unit, Decimal('50.00'))

    def test_void_purchase_reverses_stock(self):
        purchase = create_purchase_order({
            'invoice_number': 'INV-VOID-TEST',
            'purchase_date': self.entry_date,
            'supplier_name': 'Local Supplier',
            'amount_paid': '100.00',
        }, [{
            'product_id': self.p1.id,
            'quantity_purchased': '15.00',
            'purchase_cost_per_unit': '40.00',
        }])
        self.assertEqual(self.p1.current_stock, Decimal('25.00'))

        void_purchase_order(purchase, reason='Defective consignment rejected')
        self.assertEqual(purchase.status, 'voided')
        self.assertEqual(self.p1.current_stock, Decimal('10.00'))  # Reverted to 10
