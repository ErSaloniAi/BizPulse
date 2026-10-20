from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Sale, SaleItem
from inventory.models import Product, StockMovement


def generate_next_bill_number():
    """
    Generates a suggested next sequential bill number e.g. BILL-0001.
    """
    last_sale = Sale.objects.order_by('-id').first()
    if not last_sale:
        return "BILL-0001"
    try:
        if last_sale.bill_number.startswith('BILL-'):
            last_num = int(last_sale.bill_number.split('-')[-1])
            return f"BILL-{last_num + 1:04d}"
    except (ValueError, IndexError):
        pass
    return f"BILL-{last_sale.id + 1:04d}"


@transaction.atomic
def create_sale_bill(sale_data, items_data):
    """
    Atomically creates a sales bill and its items, validates stock availability,
    records negative stock movements, and captures the weighted average cost at sale time.
    """
    bill_number = sale_data.get('bill_number', '').strip()
    if not bill_number:
        raise ValidationError("Bill number is required.")

    if Sale.objects.filter(bill_number__iexact=bill_number).exists():
        raise ValidationError(f"A bill with number '{bill_number}' already exists.")

    if not items_data:
        raise ValidationError("At least one product item is required to create a bill.")

    # 1. First validate stock for all items
    validated_items = []
    for idx, item in enumerate(items_data, start=1):
        product_id = item.get('product_id')
        if not product_id:
            raise ValidationError(f"Row {idx}: Product must be selected.")

        try:
            product = Product.objects.select_for_update().get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            raise ValidationError(f"Row {idx}: Selected product does not exist.")

        try:
            qty = Decimal(str(item.get('quantity', '0')))
        except Exception:
            raise ValidationError(f"Row {idx}: Invalid quantity.")

        if qty <= Decimal('0.00'):
            raise ValidationError(f"Row {idx}: Quantity must be greater than zero.")

        try:
            price = Decimal(str(item.get('actual_selling_price_per_unit', '0')))
        except Exception:
            raise ValidationError(f"Row {idx}: Invalid selling price.")

        if price < Decimal('0.00'):
            raise ValidationError(f"Row {idx}: Selling price cannot be negative.")

        try:
            discount = Decimal(str(item.get('discount_amount', '0') or '0'))
        except Exception:
            discount = Decimal('0.00')

        if discount < Decimal('0.00'):
            raise ValidationError(f"Row {idx}: Discount cannot be negative.")

        current_avail = product.current_stock
        if qty > current_avail:
            raise ValidationError(
                f"Row {idx}: Cannot sell {qty} {product.get_unit_display()} of '{product.name}'. "
                f"Only {current_avail} {product.get_unit_display()} available in stock."
            )

        raw_subtotal = (qty * price) - discount
        line_subtotal = max(raw_subtotal, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if raw_subtotal < Decimal('0.00'):
            raise ValidationError(f"Row {idx}: Line total cannot be negative after discount.")

        validated_items.append({
            'product': product,
            'quantity': qty,
            'price': price,
            'discount': discount,
            'line_total': line_subtotal,
            'unit_cost': product.weighted_avg_cost,  # Snapshot historical cost
        })

    # 2. Compute bill total
    total_bill_amount = sum(item['line_total'] for item in validated_items)

    amount_paid = Decimal(str(sale_data.get('amount_paid', '0') or '0'))
    if amount_paid < Decimal('0.00'):
        raise ValidationError("Amount paid cannot be negative.")
    if amount_paid > total_bill_amount:
        raise ValidationError("Amount paid cannot exceed total bill amount.")

    # Determine payment status
    if amount_paid >= total_bill_amount and total_bill_amount > Decimal('0.00'):
        payment_status = 'paid'
        outstanding_amount = Decimal('0.00')
    elif amount_paid > Decimal('0.00'):
        payment_status = 'partial'
        outstanding_amount = total_bill_amount - amount_paid
    else:
        payment_status = sale_data.get('payment_status', 'unpaid')
        outstanding_amount = total_bill_amount

    # 3. Create Sale record
    sale = Sale.objects.create(
        bill_number=bill_number,
        sale_date=sale_data.get('sale_date') or timezone.localdate(),
        customer_name=(sale_data.get('customer_name') or '').strip(),
        total_amount=total_bill_amount,
        payment_status=payment_status,
        amount_paid=amount_paid,
        outstanding_amount=outstanding_amount,
        payment_method=sale_data.get('payment_method') or 'cash',
        status='confirmed',
        notes=(sale_data.get('notes') or '').strip(),
    )

    # 4. Create SaleItems and StockMovements
    for item in validated_items:
        SaleItem.objects.create(
            sale=sale,
            product=item['product'],
            quantity_sold=item['quantity'],
            actual_selling_price_per_unit=item['price'],
            historical_cost_per_unit=item['unit_cost'],
            discount_amount=item['discount'],
            line_total=item['line_total'],
        )

        StockMovement.objects.create(
            product=item['product'],
            movement_type='SALE',
            quantity=-item['quantity'],  # Negative stock deduction
            unit_cost=item['unit_cost'],
            reference_number=f"Bill #{sale.bill_number}",
            date=sale.sale_date,
            notes=f"Sold to {sale.customer_name or 'Walk-in Customer'}"
        )

    return sale


@transaction.atomic
def void_sale_bill(sale, reason=''):
    """
    Voids a confirmed sales bill and reverses the stock deductions.
    Financial records are marked as voided rather than permanently deleted.
    """
    if sale.status == 'voided':
        raise ValidationError("This bill is already voided.")

    # Restore stock for each item
    for item in sale.items.all():
        StockMovement.objects.create(
            product=item.product,
            movement_type='RETURN_IN',
            quantity=item.quantity_sold,  # Positive reversal
            unit_cost=item.historical_cost_per_unit,
            reference_number=f"VOID-{sale.bill_number}",
            date=timezone.localdate(),
            notes=f"Voided Bill #{sale.bill_number}. Reason: {reason}"
        )

    sale.status = 'voided'
    sale.notes = (sale.notes + f"\n[Voided on {timezone.localdate()}: {reason}]").strip()
    sale.save(update_fields=['status', 'notes', 'updated_at'])
    return sale
