from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from config.csv_utils import (
    get_normalized_dict_reader,
    parse_decimal_safe,
    parse_date_safe,
    generate_csv_download,
)
from .models import Product, StockMovement
from .services import create_product_with_opening_stock


def get_field_val(row, candidates, default=''):
    for cand in candidates:
        if cand in row and row[cand]:
            return row[cand]
    return default


def normalize_unit(unit_str):
    if not unit_str:
        return 'piece'
    u = unit_str.strip().lower()
    valid_units = dict(Product.UNIT_CHOICES)
    if u in valid_units:
        return u
    for k, v in valid_units.items():
        if u in v.lower():
            return k
    return 'piece'


def import_products_from_csv(uploaded_file):
    """
    Parses and imports products and opening stock records from an uploaded CSV file.
    Returns (created_count, updated_count, errors_list).
    """
    rows = get_normalized_dict_reader(uploaded_file)
    if not rows:
        return 0, 0, ["The uploaded CSV file is empty or missing valid headers."]

    created_count = 0
    updated_count = 0
    errors = []

    with transaction.atomic():
        for row in rows:
            row_num = row.get('_row_num', '?')
            name = get_field_val(row, ['product_name', 'name', 'item_name', 'item', 'product'])
            if not name:
                errors.append(f"Row {row_num}: Product Name is missing.")
                continue

            brand = get_field_val(row, ['brand', 'company', 'make'])
            category = get_field_val(row, ['category', 'product_category', 'type'])
            supplier_name = get_field_val(row, ['supplier_name', 'supplier', 'vendor'])
            raw_unit = get_field_val(row, ['unit', 'unit_of_measure', 'uom'])
            unit = normalize_unit(raw_unit)

            try:
                opening_qty = parse_decimal_safe(
                    get_field_val(row, ['opening_quantity', 'available_quantity', 'quantity', 'stock', 'qty']),
                    Decimal('0.00')
                )
                if opening_qty < Decimal('0.00'):
                    errors.append(f"Row {row_num}: Opening stock quantity cannot be negative.")
                    continue
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            try:
                cost_price = parse_decimal_safe(
                    get_field_val(row, ['purchase_cost_per_unit', 'purchase_cost', 'cost_price', 'cost', 'purchase_rate']),
                    Decimal('0.00')
                )
                if cost_price < Decimal('0.00'):
                    errors.append(f"Row {row_num}: Purchase cost cannot be negative.")
                    continue
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            try:
                selling_price = parse_decimal_safe(
                    get_field_val(row, ['selling_price_per_unit', 'selling_price', 'sale_price', 'mrp', 'rate']),
                    cost_price  # fallback to cost price if not specified
                )
                if selling_price < Decimal('0.00'):
                    errors.append(f"Row {row_num}: Selling price cannot be negative.")
                    continue
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            try:
                min_stock = parse_decimal_safe(
                    get_field_val(row, ['minimum_stock_level', 'min_stock', 'threshold', 'low_stock_limit']),
                    Decimal('5.00')
                )
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            try:
                entry_date = parse_date_safe(
                    get_field_val(row, ['stock_entry_date', 'entry_date', 'date']),
                    timezone.localdate()
                )
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            # Check if matching product already exists
            existing = Product.objects.filter(
                name__iexact=name.strip(),
                brand__iexact=brand.strip(),
                unit=unit,
                is_active=True
            ).first()

            if existing:
                # Update details and recalculate weighted average cost if stock added
                if category and not existing.category:
                    existing.category = category
                if supplier_name and not existing.supplier_name:
                    existing.supplier_name = supplier_name
                if selling_price > Decimal('0.00'):
                    existing.selling_price_per_unit = selling_price
                if cost_price > Decimal('0.00'):
                    existing.purchase_cost_per_unit = cost_price
                if min_stock > Decimal('0.00'):
                    existing.minimum_stock_level = min_stock

                if opening_qty > Decimal('0.00'):
                    curr_stock = existing.current_stock
                    curr_avg = existing.weighted_avg_cost
                    import_cost = cost_price if cost_price > Decimal('0.00') else curr_avg

                    if curr_stock > Decimal('0.00'):
                        new_avg = ((curr_stock * curr_avg) + (opening_qty * import_cost)) / (curr_stock + opening_qty)
                    else:
                        new_avg = import_cost

                    existing.weighted_avg_cost = round(new_avg, 4)
                    existing.save()

                    StockMovement.objects.create(
                        product=existing,
                        movement_type='ADJUSTMENT',
                        quantity=opening_qty,
                        unit_cost=import_cost,
                        reference_number=f"CSV-IMPORT-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                        date=entry_date,
                        notes='Stock added via CSV import'
                    )
                else:
                    existing.save()

                updated_count += 1
            else:
                cleaned_data = {
                    'name': name,
                    'brand': brand,
                    'category': category,
                    'supplier_name': supplier_name,
                    'unit': unit,
                    'opening_quantity': opening_qty,
                    'purchase_cost_per_unit': cost_price,
                    'selling_price_per_unit': selling_price,
                    'minimum_stock_level': min_stock,
                    'stock_entry_date': entry_date,
                }
                create_product_with_opening_stock(cleaned_data)
                created_count += 1

    return created_count, updated_count, errors


def get_product_sample_csv():
    headers = [
        "Product Name", "Brand", "Category", "Supplier Name", "Unit",
        "Opening Quantity", "Purchase Cost Per Unit", "Selling Price Per Unit",
        "Minimum Stock Level", "Stock Entry Date"
    ]
    sample_rows = [
        ["Classmate 200 Pgs Ruled Notebook", "ITC", "Notebooks", "Vikas Traders", "Piece", "50", "45.00", "60.00", "10", "2026-10-01"],
        ["Reynolds 045 Fine Ball Pen (Pack of 5)", "Reynolds", "Pens", "National Distributors", "Packet", "30", "35.00", "50.00", "5", "2026-10-01"],
        ["A4 Copier Paper 75 GSM Ream", "JK Copier", "Paper & Printing", "Agarwal Papers", "Ream", "25", "240.00", "300.00", "5", "2026-10-01"],
        ["Camel Plastic Crayons 16 Shades", "Kokuyo Camlin", "Art Supplies", "Stationery World", "Box", "20", "55.00", "80.00", "4", "2026-10-01"],
        ["Doms Eraser (Jar of 20)", "Doms", "Erasers", "Stationery World", "Box", "15", "60.00", "100.00", "3", "2026-10-01"],
    ]
    return generate_csv_download("bizpulse_stock_sample.csv", headers, sample_rows)
