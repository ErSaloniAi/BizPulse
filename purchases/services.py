from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Purchase, PurchaseItem
from inventory.models import Product, StockMovement


@transaction.atomic
def create_purchase_order(purchase_data, items_data):
    """
    Atomically creates a purchase invoice and its items, increments stock,
    updates the latest purchase cost on the product, and recalculates the
    weighted-average cost per unit.
    """
    supplier_name = purchase_data.get('supplier_name', '').strip()
    if not supplier_name:
        raise ValidationError("Supplier name is required.")

    if not items_data:
        raise ValidationError("At least one product item is required for a purchase.")

    # 1. Validate items
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
            qty = Decimal(str(item.get('quantity_purchased', '0')))
        except Exception:
            raise ValidationError(f"Row {idx}: Invalid quantity.")

        if qty <= Decimal('0.00'):
            raise ValidationError(f"Row {idx}: Quantity must be greater than zero.")

        try:
            cost = Decimal(str(item.get('purchase_cost_per_unit', '0')))
        except Exception:
            raise ValidationError(f"Row {idx}: Invalid cost per unit.")

        if cost < Decimal('0.00'):
            raise ValidationError(f"Row {idx}: Cost per unit cannot be negative.")

        line_total = (qty * cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        validated_items.append({
            'product': product,
            'quantity': qty,
            'cost': cost,
            'line_total': line_total,
        })

    # 2. Compute purchase totals
    total_purchase_amount = sum(item['line_total'] for item in validated_items)

    amount_paid = Decimal(str(purchase_data.get('amount_paid', '0') or '0'))
    if amount_paid < Decimal('0.00'):
        raise ValidationError("Amount paid cannot be negative.")
    if amount_paid > total_purchase_amount:
        raise ValidationError("Amount paid cannot exceed total purchase amount.")

    if amount_paid >= total_purchase_amount and total_purchase_amount > Decimal('0.00'):
        payment_status = 'paid'
        outstanding_amount = Decimal('0.00')
    elif amount_paid > Decimal('0.00'):
        payment_status = 'partial'
        outstanding_amount = total_purchase_amount - amount_paid
    else:
        payment_status = purchase_data.get('payment_status', 'unpaid')
        outstanding_amount = total_purchase_amount

    # 3. Create Purchase record
    purchase = Purchase.objects.create(
        invoice_number=(purchase_data.get('invoice_number') or '').strip(),
        purchase_date=purchase_data.get('purchase_date') or timezone.localdate(),
        supplier_name=supplier_name,
        total_amount=total_purchase_amount,
        payment_status=payment_status,
        amount_paid=amount_paid,
        outstanding_amount=outstanding_amount,
        payment_method=purchase_data.get('payment_method') or 'cash',
        status='confirmed',
        notes=(purchase_data.get('notes') or '').strip(),
    )

    # 4. Create PurchaseItems, update weighted average cost, and record StockMovement
    for item in validated_items:
        prod = item['product']
        qty = item['quantity']
        cost = item['cost']

        PurchaseItem.objects.create(
            purchase=purchase,
            product=prod,
            quantity_purchased=qty,
            purchase_cost_per_unit=cost,
            line_total=item['line_total'],
        )

        # Recalculate moving weighted-average cost
        current_stock = prod.current_stock
        current_avg_cost = prod.weighted_avg_cost

        if current_stock > Decimal('0.00'):
            new_weighted_avg = (
                (current_stock * current_avg_cost) + (qty * cost)
            ) / (current_stock + qty)
        else:
            new_weighted_avg = cost

        prod.weighted_avg_cost = round(new_weighted_avg, 4)
        prod.purchase_cost_per_unit = cost  # Update latest purchase cost
        prod.save(update_fields=['weighted_avg_cost', 'purchase_cost_per_unit', 'updated_at'])

        # Increment stock
        StockMovement.objects.create(
            product=prod,
            movement_type='PURCHASE',
            quantity=qty,  # Positive stock addition
            unit_cost=cost,
            reference_number=f"Invoice #{purchase.invoice_number or purchase.id}",
            date=purchase.purchase_date,
            notes=f"Purchased from {purchase.supplier_name}"
        )

    return purchase


@transaction.atomic
def void_purchase_order(purchase, reason=''):
    """
    Voids a confirmed purchase invoice and reverses the stock addition.
    """
    if purchase.status == 'voided':
        raise ValidationError("This purchase invoice is already voided.")

    # Check that deducting stock will not result in negative stock
    for item in purchase.items.select_related('product').all():
        if item.product.current_stock < item.quantity_purchased:
            raise ValidationError(
                f"Cannot void purchase #{purchase.id}: {item.quantity_purchased} {item.product.get_unit_display()} of "
                f"'{item.product.name}' was purchased, but current stock is only {item.product.current_stock}. "
                f"Some units from this purchase have already been sold."
            )

    # Deduct stock for each item and recalculate weighted average cost
    for item in purchase.items.select_related('product').all():
        prod = item.product
        current_stock = prod.current_stock  # stock before deducting this purchase
        qty = item.quantity_purchased
        cost = item.purchase_cost_per_unit

        remaining_stock = current_stock - qty
        if remaining_stock > Decimal('0.00'):
            prior_total_cost = (current_stock * prod.weighted_avg_cost) - (qty * cost)
            if prior_total_cost > Decimal('0.00'):
                prod.weighted_avg_cost = round(prior_total_cost / remaining_stock, 4)
            else:
                prod.weighted_avg_cost = prod.purchase_cost_per_unit
        else:
            prod.weighted_avg_cost = prod.purchase_cost_per_unit

        prod.save(update_fields=['weighted_avg_cost', 'updated_at'])

        StockMovement.objects.create(
            product=prod,
            movement_type='RETURN_OUT',
            quantity=-qty,  # Negative reversal
            unit_cost=cost,
            reference_number=f"VOID-PURCHASE-{purchase.id}",
            date=timezone.localdate(),
            notes=f"Voided Purchase #{purchase.id}. Reason: {reason}"
        )

    purchase.status = 'voided'
    purchase.notes = (purchase.notes + f"\n[Voided on {timezone.localdate()}: {reason}]").strip()
    purchase.save(update_fields=['status', 'notes', 'updated_at'])
    return purchase
