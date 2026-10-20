from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from .models import Product, StockMovement


def check_duplicate_product(name, brand='', unit='piece', exclude_pk=None):
    """
    Check if a product with the same name, brand, and unit already exists (case-insensitive).
    """
    query = Product.objects.filter(
        name__iexact=name.strip(),
        brand__iexact=(brand or '').strip(),
        unit=unit,
        is_active=True
    )
    if exclude_pk:
        query = query.exclude(pk=exclude_pk)
    return query.first()


@transaction.atomic
def create_product_with_opening_stock(cleaned_data):
    """
    Creates a product and records its opening stock movement atomically.
    """
    product = Product(
        name=cleaned_data['name'].strip(),
        brand=(cleaned_data.get('brand') or '').strip(),
        category=(cleaned_data.get('category') or '').strip(),
        supplier_name=(cleaned_data.get('supplier_name') or '').strip(),
        unit=cleaned_data.get('unit', 'piece'),
        opening_quantity=cleaned_data.get('opening_quantity', Decimal('0.00')),
        purchase_cost_per_unit=cleaned_data.get('purchase_cost_per_unit', Decimal('0.00')),
        selling_price_per_unit=cleaned_data.get('selling_price_per_unit', Decimal('0.00')),
        weighted_avg_cost=cleaned_data.get('purchase_cost_per_unit', Decimal('0.00')),
        minimum_stock_level=cleaned_data.get('minimum_stock_level', Decimal('5.00')),
        stock_entry_date=cleaned_data['stock_entry_date'],
        is_active=True,
    )
    product.save()

    # If opening stock is greater than 0, create OPENING stock movement
    if product.opening_quantity > Decimal('0.00'):
        StockMovement.objects.create(
            product=product,
            movement_type='OPENING',
            quantity=product.opening_quantity,
            unit_cost=product.purchase_cost_per_unit,
            reference_number=f"OPENING-{product.product_code}",
            date=product.stock_entry_date,
            notes='Initial opening stock baseline'
        )

    return product


@transaction.atomic
def record_stock_adjustment(product, adjustment_type, quantity, date, reason='', notes=''):
    """
    Records a manual stock adjustment or write-off atomically.
    adjustment_type: 'ADD' or 'SUBTRACT'
    """
    qty = Decimal(str(quantity))
    if adjustment_type == 'SUBTRACT':
        qty = -abs(qty)
        movement_type = 'WRITE_OFF' if 'damage' in reason.lower() or 'loss' in reason.lower() else 'ADJUSTMENT'
    else:
        qty = abs(qty)
        movement_type = 'ADJUSTMENT'

    movement = StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=qty,
        unit_cost=product.weighted_avg_cost,
        reference_number=reason[:100] if reason else 'MANUAL-ADJUSTMENT',
        date=date,
        notes=notes
    )
    return movement


def get_all_product_stock_summary():
    """
    Returns an annotated queryset of products with aggregated stock counts and low-stock flags.
    """
    products = Product.objects.filter(is_active=True).prefetch_related('stock_movements')
    summary_list = []
    for p in products:
        current = p.current_stock
        summary_list.append({
            'product': p,
            'current_stock': current,
            'is_low_stock': current <= p.minimum_stock_level,
            'stock_value': current * p.weighted_avg_cost,
        })
    return summary_list
