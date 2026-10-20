import io
from decimal import Decimal
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from inventory.models import Product, StockMovement
from purchases.models import Purchase, PurchaseItem
from sales.models import Sale, SaleItem
from expenses.models import Expense, ExpenseCategory


class CSVUploadTests(TestCase):
    def setUp(self):
        self.client = Client()

    # ---------------------------------------------------------
    # 1. Inventory / Stock Record CSV Upload Tests
    # ---------------------------------------------------------
    def test_inventory_sample_csv_download(self):
        response = self.client.get('/inventory/sample-csv/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Product Name', content)
        self.assertIn('Opening Quantity', content)

    def test_inventory_csv_upload_valid(self):
        csv_data = (
            "Product Name,Brand,Category,Supplier Name,Unit,Opening Quantity,Purchase Cost Per Unit,Selling Price Per Unit,Minimum Stock Level,Stock Entry Date\n"
            "Parker Vector Pen,Parker,Pens,National Dist,Piece,40,150.00,200.00,5,2026-10-01\n"
            "Camlin Geometry Box,Camlin,Geometry,Stationery World,Box,25,80.00,110.00,3,2026-10-01\n"
        )
        uploaded_file = SimpleUploadedFile("stock.csv", csv_data.encode('utf-8'), content_type="text/csv")
        response = self.client.post('/inventory/upload-csv/', {'csv_file': uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify products in DB
        pen = Product.objects.get(name='Parker Vector Pen')
        self.assertEqual(pen.brand, 'Parker')
        self.assertEqual(pen.current_stock, Decimal('40.00'))
        self.assertEqual(pen.purchase_cost_per_unit, Decimal('150.00'))
        self.assertEqual(pen.selling_price_per_unit, Decimal('200.00'))

        geom = Product.objects.get(name='Camlin Geometry Box')
        self.assertEqual(geom.current_stock, Decimal('25.00'))
        self.assertEqual(geom.unit, 'box')

    def test_inventory_csv_upload_update_existing_product(self):
        # Create an existing product first
        Product.objects.create(
            name='Test Notebook',
            brand='Classmate',
            unit='piece',
            opening_quantity=Decimal('10.00'),
            purchase_cost_per_unit=Decimal('30.00'),
            selling_price_per_unit=Decimal('40.00'),
            weighted_avg_cost=Decimal('30.00'),
            minimum_stock_level=Decimal('5.00'),
            stock_entry_date='2026-10-01',
            is_active=True
        )

        csv_data = (
            "Product Name,Brand,Category,Unit,Opening Quantity,Purchase Cost Per Unit,Selling Price Per Unit\n"
            "Test Notebook,Classmate,Notebooks,Piece,20,32.00,45.00\n"
        )
        uploaded_file = SimpleUploadedFile("update_stock.csv", csv_data.encode('utf-8'), content_type="text/csv")
        response = self.client.post('/inventory/upload-csv/', {'csv_file': uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Existing product should now have updated category/price and stock addition
        prod = Product.objects.get(name='Test Notebook')
        self.assertEqual(prod.category, 'Notebooks')
        self.assertEqual(prod.selling_price_per_unit, Decimal('45.00'))

    # ---------------------------------------------------------
    # 2. Purchases CSV Upload Tests
    # ---------------------------------------------------------
    def test_purchases_sample_csv_download(self):
        response = self.client.get('/purchases/sample-csv/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Invoice Number', content)
        self.assertIn('Supplier Name', content)

    def test_purchases_csv_upload_valid_and_grouped(self):
        csv_data = (
            "Invoice Number,Purchase Date,Supplier Name,Product Name,Quantity,Purchase Cost Per Unit,Payment Status,Amount Paid,Payment Method,Notes\n"
            "INV-9901,2026-10-05,Royal Suppliers,Fevicol 100g,50,20.00,paid,1000.00,cash,Batch A\n"
            "INV-9901,2026-10-05,Royal Suppliers,Cello Gripper Pen,100,7.00,paid,700.00,cash,Batch A\n"
        )
        uploaded_file = SimpleUploadedFile("purchases.csv", csv_data.encode('utf-8'), content_type="text/csv")
        response = self.client.post('/purchases/upload-csv/', {'csv_file': uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Invoices should be grouped into 1 Purchase with 2 items
        purchase = Purchase.objects.get(invoice_number='INV-9901')
        self.assertEqual(purchase.supplier_name, 'Royal Suppliers')
        self.assertEqual(purchase.items.count(), 2)
        self.assertEqual(purchase.total_amount, Decimal('1700.00'))

        # Products should have been created and stock updated
        fevicol = Product.objects.get(name='Fevicol 100g')
        self.assertEqual(fevicol.current_stock, Decimal('50.00'))
        self.assertEqual(fevicol.purchase_cost_per_unit, Decimal('20.00'))

        cello = Product.objects.get(name='Cello Gripper Pen')
        self.assertEqual(cello.current_stock, Decimal('100.00'))

    # ---------------------------------------------------------
    # 3. Sales CSV Upload Tests
    # ---------------------------------------------------------
    def test_sales_sample_csv_download(self):
        response = self.client.get('/sales/sample-csv/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Bill Number', content)
        self.assertIn('Product Name', content)

    def test_sales_csv_upload_valid_and_stock_deduction(self):
        # Create product with stock
        prod = Product.objects.create(
            name='Pilot Pen Hi-Tech',
            unit='piece',
            opening_quantity=Decimal('30.00'),
            purchase_cost_per_unit=Decimal('50.00'),
            selling_price_per_unit=Decimal('70.00'),
            weighted_avg_cost=Decimal('50.00'),
            minimum_stock_level=Decimal('5.00'),
            stock_entry_date='2026-10-01',
            is_active=True
        )
        StockMovement.objects.create(
            product=prod,
            movement_type='OPENING',
            quantity=Decimal('30.00'),
            unit_cost=Decimal('50.00'),
            date='2026-10-01'
        )

        csv_data = (
            "Bill Number,Sale Date,Customer Name,Product Name,Quantity,Selling Price Per Unit,Discount Amount,Payment Status,Payment Method\n"
            "BILL-8001,2026-10-10,Rohan Mehta,Pilot Pen Hi-Tech,5,70.00,0.00,paid,cash\n"
        )
        uploaded_file = SimpleUploadedFile("sales.csv", csv_data.encode('utf-8'), content_type="text/csv")
        response = self.client.post('/sales/upload-csv/', {'csv_file': uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Sale bill should be recorded
        sale = Sale.objects.get(bill_number='BILL-8001')
        self.assertEqual(sale.customer_name, 'Rohan Mehta')
        self.assertEqual(sale.total_amount, Decimal('350.00'))

        # Stock should be deducted from 30 to 25
        prod.refresh_from_db()
        self.assertEqual(prod.current_stock, Decimal('25.00'))

    def test_sales_csv_upload_insufficient_stock_error(self):
        prod = Product.objects.create(
            name='Scientific Calculator',
            unit='piece',
            opening_quantity=Decimal('2.00'),
            purchase_cost_per_unit=Decimal('500.00'),
            selling_price_per_unit=Decimal('750.00'),
            weighted_avg_cost=Decimal('500.00'),
            stock_entry_date='2026-10-01',
            is_active=True
        )
        StockMovement.objects.create(
            product=prod,
            movement_type='OPENING',
            quantity=Decimal('2.00'),
            unit_cost=Decimal('500.00'),
            date='2026-10-01'
        )

        # Request 10 units when only 2 are available
        csv_data = (
            "Bill Number,Sale Date,Customer Name,Product Name,Quantity,Selling Price Per Unit\n"
            "BILL-9999,2026-10-10,Student,Scientific Calculator,10,750.00\n"
        )
        uploaded_file = SimpleUploadedFile("insufficient_sales.csv", csv_data.encode('utf-8'), content_type="text/csv")
        response = self.client.post('/sales/upload-csv/', {'csv_file': uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Bill must NOT have been created
        self.assertFalse(Sale.objects.filter(bill_number='BILL-9999').exists())
        # Stock must remain intact
        prod.refresh_from_db()
        self.assertEqual(prod.current_stock, Decimal('2.00'))

    # ---------------------------------------------------------
    # 4. Expenses CSV Upload Tests
    # ---------------------------------------------------------
    def test_expenses_sample_csv_download(self):
        response = self.client.get('/expenses/sample-csv/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Description', content)
        self.assertIn('Amount', content)

    def test_expenses_csv_upload_valid_and_auto_category(self):
        csv_data = (
            "Date,Category,Description,Amount,Payment Status,Amount Paid,Payment Method,Paid To,Receipt Reference,Notes\n"
            "2026-10-02,Internet & Wifi,Monthly broadband connection,1180.00,paid,1180.00,upi,Airtel Fibernet,BILL-1234,Fiber connection\n"
            "2026-10-03,Tea & Refreshments,Daily snacks,150.00,paid,150.00,cash,Tea Stall,,Daily expense\n"
        )
        uploaded_file = SimpleUploadedFile("expenses.csv", csv_data.encode('utf-8'), content_type="text/csv")
        response = self.client.post('/expenses/upload-csv/', {'csv_file': uploaded_file}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Auto-created category
        self.assertTrue(ExpenseCategory.objects.filter(name='Internet & Wifi').exists())

        # Expenses in DB
        expense = Expense.objects.get(description='Monthly broadband connection')
        self.assertEqual(expense.amount, Decimal('1180.00'))
        self.assertEqual(expense.paid_to, 'Airtel Fibernet')
        self.assertEqual(expense.payment_status, 'paid')
