from decimal import Decimal
import datetime
from django.test import TestCase
from inventory.models import Product, StockMovement
from inventory.services import (
    create_product_with_opening_stock,
    check_duplicate_product,
    record_stock_adjustment,
)


class InventoryTests(TestCase):
    def setUp(self):
        self.entry_date = datetime.date(2026, 1, 1)

    def test_create_product_with_opening_stock(self):
        data = {
            'name': 'Classmate Notebook 200 Pgs',
            'brand': 'ITC Classmate',
            'category': 'Notebooks',
            'supplier_name': 'Stationery Hub',
            'unit': 'piece',
            'opening_quantity': Decimal('50.00'),
            'purchase_cost_per_unit': Decimal('40.00'),
            'selling_price_per_unit': Decimal('60.00'),
            'minimum_stock_level': Decimal('10.00'),
            'stock_entry_date': self.entry_date,
        }
        product = create_product_with_opening_stock(data)

        self.assertIsNotNone(product.pk)
        self.assertTrue(product.product_code.startswith('PRD-'))
        self.assertEqual(product.current_stock, Decimal('50.00'))
        self.assertEqual(product.weighted_avg_cost, Decimal('40.00'))
        self.assertFalse(product.is_low_stock)

        # Check StockMovement was recorded
        movements = product.stock_movements.all()
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().movement_type, 'OPENING')
        self.assertEqual(movements.first().quantity, Decimal('50.00'))

    def test_duplicate_product_check(self):
        data = {
            'name': 'Reynolds 045 Pen',
            'brand': 'Reynolds',
            'unit': 'piece',
            'opening_quantity': Decimal('100.00'),
            'purchase_cost_per_unit': Decimal('7.00'),
            'selling_price_per_unit': Decimal('10.00'),
            'stock_entry_date': self.entry_date,
        }
        create_product_with_opening_stock(data)

        # Check duplicate with same case
        dup = check_duplicate_product(name='Reynolds 045 Pen', brand='Reynolds', unit='piece')
        self.assertIsNotNone(dup)

        # Check duplicate with case-insensitive variation
        dup_case = check_duplicate_product(name='reynolds 045 pen', brand='REYNOLDS', unit='piece')
        self.assertIsNotNone(dup_case)

        # Different brand should not be duplicate
        not_dup = check_duplicate_product(name='Reynolds 045 Pen', brand='Cello', unit='piece')
        self.assertIsNone(not_dup)

    def test_low_stock_detection(self):
        data = {
            'name': 'A4 Copier Paper',
            'brand': 'JK Copier',
            'unit': 'ream',
            'opening_quantity': Decimal('4.00'),
            'purchase_cost_per_unit': Decimal('280.00'),
            'selling_price_per_unit': Decimal('350.00'),
            'minimum_stock_level': Decimal('5.00'),
            'stock_entry_date': self.entry_date,
        }
        product = create_product_with_opening_stock(data)
        self.assertTrue(product.is_low_stock)
        self.assertEqual(product.stock_value, Decimal('4.00') * Decimal('280.00'))

    def test_stock_adjustment(self):
        data = {
            'name': 'Marker Pen Black',
            'brand': 'Camlin',
            'unit': 'piece',
            'opening_quantity': Decimal('20.00'),
            'purchase_cost_per_unit': Decimal('15.00'),
            'selling_price_per_unit': Decimal('25.00'),
            'stock_entry_date': self.entry_date,
        }
        product = create_product_with_opening_stock(data)

        # Add stock via adjustment
        record_stock_adjustment(product, 'ADD', Decimal('5.00'), self.entry_date, 'Found extra stock')
        self.assertEqual(product.current_stock, Decimal('25.00'))

        # Deduct stock for damage
        record_stock_adjustment(product, 'SUBTRACT', Decimal('3.00'), self.entry_date, 'Water damage')
        self.assertEqual(product.current_stock, Decimal('22.00'))
