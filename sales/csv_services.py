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
from .models import Sale, SaleItem
from .services import create_sale_bill, generate_next_bill_number
from inventory.models import Product


def get_field_val(row, candidates, default=''):
    for cand in candidates:
        if cand in row and row[cand]:
            return row[cand]
    return default


def import_sales_from_csv(uploaded_file):
    """
    Parses and imports sales bills and updates inventory stock.
    Supports grouping multiple product items under the same bill number.
    Returns (created_bills_count, total_items_count, errors_list).
    """
    rows = get_normalized_dict_reader(uploaded_file)
    if not rows:
        return 0, 0, ["The uploaded CSV file is empty or missing valid headers."]

    errors = []
    grouped_bills = OrderedDict()

    for row in rows:
        row_num = row.get('_row_num', '?')
        product_name = get_field_val(row, ['product_name', 'product', 'item_name', 'item'])
        if not product_name:
            errors.append(f"Row {row_num}: Product Name is required.")
            continue

        try:
            qty = parse_decimal_safe(
                get_field_val(row, ['quantity', 'qty', 'quantity_sold', 'units']),
                Decimal('0.00')
            )
            if qty <= Decimal('0.00'):
                errors.append(f"Row {row_num}: Quantity sold must be greater than zero.")
                continue
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        try:
            sale_date = parse_date_safe(
                get_field_val(row, ['sale_date', 'date', 'bill_date']),
                timezone.localdate()
            )
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        # Look up product in inventory
        clean_name = product_name.strip()
        product = Product.objects.filter(name__iexact=clean_name, is_active=True).first()
        if not product:
            product = Product.objects.filter(product_code__iexact=clean_name, is_active=True).first()

        if not product:
            errors.append(f"Row {row_num}: Product '{clean_name}' does not exist in inventory. Please add it first.")
            continue

        try:
            selling_price = parse_decimal_safe(
                get_field_val(row, ['selling_price_per_unit', 'selling_price', 'rate', 'price', 'mrp']),
                product.selling_price_per_unit
            )
            if selling_price < Decimal('0.00'):
                errors.append(f"Row {row_num}: Selling price cannot be negative.")
                continue
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        try:
            discount = parse_decimal_safe(
                get_field_val(row, ['discount_amount', 'discount', 'disc']),
                Decimal('0.00')
            )
        except ValueError as e:
            errors.append(f"Row {row_num}: {str(e)}")
            continue

        customer_name = get_field_val(row, ['customer_name', 'customer', 'client'], 'Walk-in Customer')
        bill_num = get_field_val(row, ['bill_number', 'bill_no', 'invoice_number', 'receipt_no', 'bill'])
        if not bill_num:
            bill_num = f"BILL-{sale_date.strftime('%Y%m%d')}-{customer_name[:6].upper().replace(' ', '')}"

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

        # Group key: (bill_num, customer_name, sale_date)
        group_key = (bill_num, customer_name, sale_date)
        if group_key not in grouped_bills:
            grouped_bills[group_key] = {
                'bill_number': bill_num,
                'customer_name': customer_name,
                'sale_date': sale_date,
                'payment_status': payment_status,
                'payment_method': payment_method,
                'amount_paid': amount_paid,
                'notes': notes,
                'items': [],
            }

        grouped_bills[group_key]['items'].append({
            'row_num': row_num,
            'product': product,
            'quantity': qty,
            'price': selling_price,
            'discount': discount,
        })

    if not grouped_bills:
        return 0, 0, errors or ["No valid sales records could be parsed from the CSV."]

    bills_created = 0
    total_items_created = 0

    with transaction.atomic():
        # First ensure unique bill numbers if duplicates in DB
        for group_key, bill_data in grouped_bills.items():
            candidate_bill_num = bill_data['bill_number']
            if Sale.objects.filter(bill_number__iexact=candidate_bill_num).exists():
                candidate_bill_num = generate_next_bill_number()

            items_payload = []
            for item in bill_data['items']:
                # Stock sufficiency check
                product = item['product']
                if product.current_stock < item['quantity']:
                    errors.append(
                        f"Row {item['row_num']}: Insufficient stock for '{product.name}'. "
                        f"Available: {product.current_stock} {product.get_unit_display()}, Required: {item['quantity']}."
                    )
                    continue

                items_payload.append({
                    'product_id': product.id,
                    'quantity': item['quantity'],
                    'actual_selling_price_per_unit': item['price'],
                    'discount_amount': item['discount'],
                })

            if not items_payload:
                continue

            calculated_total = sum(
                (i['quantity'] * i['actual_selling_price_per_unit']) - i['discount_amount']
                for i in items_payload
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Resolve amount paid
            amount_paid = bill_data['amount_paid']
            payment_status = bill_data['payment_status']
            if amount_paid is None:
                if payment_status == 'paid':
                    amount_paid = calculated_total
                elif payment_status == 'unpaid':
                    amount_paid = Decimal('0.00')
                else:
                    amount_paid = calculated_total / Decimal('2.00')
            else:
                amount_paid = min(amount_paid, calculated_total)

            sale_payload = {
                'bill_number': candidate_bill_num,
                'sale_date': bill_data['sale_date'],
                'customer_name': bill_data['customer_name'],
                'payment_status': payment_status,
                'payment_method': bill_data['payment_method'],
                'amount_paid': str(amount_paid),
                'notes': bill_data['notes'],
            }

            try:
                create_sale_bill(sale_payload, items_payload)
                bills_created += 1
                total_items_created += len(items_payload)
            except Exception as e:
                errors.append(f"Bill '{candidate_bill_num}': {str(e)}")

    return bills_created, total_items_created, errors


def get_sales_sample_csv():
    headers = [
        "Bill Number", "Sale Date", "Customer Name", "Product Name",
        "Quantity", "Selling Price Per Unit", "Discount Amount", "Payment Status",
        "Amount Paid", "Payment Method", "Notes"
    ]
    sample_rows = [
        ["BILL-1001", "2026-10-10", "Rahul Verma", "Classmate 200 Pgs Ruled Notebook", "4", "60.00", "0.00", "paid", "240.00", "cash", "Counter sale"],
        ["BILL-1001", "2026-10-10", "Rahul Verma", "Reynolds 045 Fine Ball Pen (Pack of 5)", "2", "50.00", "0.00", "paid", "100.00", "cash", "Counter sale"],
        ["BILL-1002", "2026-10-10", "Sunrise Coaching Institute", "A4 Copier Paper 75 GSM Ream", "5", "300.00", "50.00", "paid", "1450.00", "upi", "Bulk discount applied"],
        ["BILL-1003", "2026-10-11", "Amit Patel", "Camel Plastic Crayons 16 Shades", "1", "80.00", "0.00", "paid", "80.00", "cash", ""],
    ]
    return generate_csv_download("bizpulse_sales_sample.csv", headers, sample_rows)
