from decimal import Decimal, ROUND_HALF_UP
from collections import OrderedDict
from django.db import transaction
from django.utils import timezone
from config.csv_utils import (
    get_normalized_dict_reader,
    parse_decimal_safe,
    parse_date_safe,
    generate_csv_download,
)
from .models import Purchase, PurchaseItem
from .services import create_purchase_order
from inventory.models import Product, StockMovement


def get_field_val(row, candidates, default=''):
    for cand in candidates:
        if cand in row and row[cand]:
            return row[cand]
    return default


def resolve_or_create_product(product_name, cost_price, entry_date):
    """
    Finds an existing product by name/code, or creates a new one automatically.
    """
    clean_name = product_name.strip()
    product = Product.objects.filter(name__iexact=clean_name, is_active=True).first()
    if not product:
        product = Product.objects.filter(product_code__iexact=clean_name, is_active=True).first()

    if not product:
        # Auto-create product for shopkeeper convenience
        product = Product.objects.create(
            name=clean_name,
            purchase_cost_per_unit=cost_price,
            selling_price_per_unit=cost_price * Decimal('1.25'),  # sensible 25% default markup
            weighted_avg_cost=cost_price,
            opening_quantity=Decimal('0.00'),
            minimum_stock_level=Decimal('5.00'),
            stock_entry_date=entry_date,
            unit='piece',
            is_active=True,
        )
    return product


def import_purchases_from_csv(uploaded_file):
    """
    Parses and imports purchase orders and updates inventory stock.
    Supports grouping multiple items under the same invoice number.
    Returns (created_invoices_count, total_items_count, errors_list).
    """
    rows = get_normalized_dict_reader(uploaded_file)
    if not rows:
        return 0, 0, ["The uploaded CSV file is empty or missing valid headers."]

    errors = []
    
    # Group rows by invoice key
    grouped_invoices = OrderedDict()

    for row in rows:
        row_num = row.get('_row_num', '?')
        supplier = get_field_val(row, ['supplier_name', 'supplier', 'vendor'])
        if not supplier:
            errors.append(f"Row {row_num}: Supplier Name is required.")
            continue

        product_name = get_field_val(row, ['product_name', 'product', 'item_name', 'item'])
        if not product_name:
            errors.append(f"Row {row_num}: Product Name is required.")
            continue

        try:
            qty = parse_decimal_safe(
                get_field_val(row, ['quantity', 'qty', 'quantity_purchased', 'units']),
                Decimal('0.00')
            )
            if qty <= Decimal('0.00'):
                errors.append(f"Row {row_num}: Quantity must be greater than zero.")
                continue
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        try:
            cost = parse_decimal_safe(
                get_field_val(row, ['purchase_cost_per_unit', 'cost_per_unit', 'purchase_cost', 'rate', 'cost', 'price']),
                Decimal('0.00')
            )
            if cost < Decimal('0.00'):
                errors.append(f"Row {row_num}: Purchase cost cannot be negative.")
                continue
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        try:
            purchase_date = parse_date_safe(
                get_field_val(row, ['purchase_date', 'date', 'invoice_date']),
                timezone.localdate()
            )
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        invoice_num = get_field_val(row, ['invoice_number', 'invoice_no', 'bill_no', 'invoice', 'ref'])
        if not invoice_num:
            invoice_num = f"PUR-{purchase_date.strftime('%Y%m%d')}-{supplier[:6].upper().replace(' ', '')}"

        payment_status = get_field_val(row, ['payment_status', 'status', 'payment'], 'paid').lower()
        if payment_status not in ('paid', 'partial', 'unpaid'):
            payment_status = 'paid'

        payment_method = get_field_val(row, ['payment_method', 'method', 'mode'], 'cash').lower()
        if payment_method not in ('cash', 'upi', 'card', 'bank', 'other'):
            payment_method = 'cash'

        amount_paid_raw = get_field_val(row, ['amount_paid', 'paid'])
        amount_paid = None
        if amount_paid_raw:
            try:
                amount_paid = parse_decimal_safe(amount_paid_raw, None)
            except ValueError:
                amount_paid = None

        notes = get_field_val(row, ['notes', 'remarks', 'comment'])

        # Group key: (invoice_num, supplier, purchase_date)
        group_key = (invoice_num, supplier, purchase_date)
        if group_key not in grouped_invoices:
            grouped_invoices[group_key] = {
                'invoice_number': invoice_num,
                'supplier_name': supplier,
                'purchase_date': purchase_date,
                'payment_status': payment_status,
                'payment_method': payment_method,
                'amount_paid': amount_paid,
                'notes': notes,
                'items': [],
            }

        grouped_invoices[group_key]['items'].append({
            'row_num': row_num,
            'product_name': product_name,
            'quantity': qty,
            'cost': cost,
            'date': purchase_date,
        })

    if not grouped_invoices:
        return 0, 0, errors or ["No valid purchase records could be parsed from the CSV."]

    invoices_created = 0
    total_items_created = 0

    with transaction.atomic():
        for group_key, inv_data in grouped_invoices.items():
            items_payload = []
            for item in inv_data['items']:
                product = resolve_or_create_product(
                    item['product_name'],
                    item['cost'],
                    item['date']
                )
                items_payload.append({
                    'product_id': product.id,
                    'quantity_purchased': item['quantity'],
                    'purchase_cost_per_unit': item['cost'],
                })

            calculated_total = sum(i['quantity_purchased'] * i['purchase_cost_per_unit'] for i in items_payload).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Resolve amount paid
            amount_paid = inv_data['amount_paid']
            payment_status = inv_data['payment_status']
            if amount_paid is None:
                if payment_status == 'paid':
                    amount_paid = calculated_total
                elif payment_status == 'unpaid':
                    amount_paid = Decimal('0.00')
                else:
                    amount_paid = calculated_total / Decimal('2.00')
            else:
                amount_paid = min(amount_paid, calculated_total)

            purchase_data = {
                'invoice_number': inv_data['invoice_number'],
                'purchase_date': inv_data['purchase_date'],
                'supplier_name': inv_data['supplier_name'],
                'payment_status': payment_status,
                'payment_method': inv_data['payment_method'],
                'amount_paid': str(amount_paid),
                'notes': inv_data['notes'],
            }

            try:
                create_purchase_order(purchase_data, items_payload)
                invoices_created += 1
                total_items_created += len(items_payload)
            except Exception as e:
                errors.append(f"Invoice '{inv_data['invoice_number']}': {str(e)}")

    return invoices_created, total_items_created, errors


def get_purchases_sample_csv():
    headers = [
        "Invoice Number", "Purchase Date", "Supplier Name", "Product Name",
        "Quantity", "Purchase Cost Per Unit", "Payment Status", "Amount Paid",
        "Payment Method", "Notes"
    ]
    sample_rows = [
        ["INV-2026-001", "2026-10-05", "Vikas Traders", "Classmate 200 Pgs Ruled Notebook", "50", "42.00", "paid", "2100.00", "upi", "Restock shipment"],
        ["INV-2026-001", "2026-10-05", "Vikas Traders", "Reynolds 045 Fine Ball Pen (Pack of 5)", "40", "32.00", "paid", "1280.00", "upi", "Restock shipment"],
        ["INV-2026-002", "2026-10-08", "Agarwal Papers", "A4 Copier Paper 75 GSM Ream", "30", "235.00", "partial", "4000.00", "bank", "Advance paid"],
        ["INV-2026-003", "2026-10-12", "Stationery World", "Camel Plastic Crayons 16 Shades", "25", "52.00", "unpaid", "0.00", "cash", "Payment due in 15 days"],
    ]
    return generate_csv_download("bizpulse_purchases_sample.csv", headers, sample_rows)
