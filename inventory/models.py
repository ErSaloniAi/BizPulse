from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Product(models.Model):
    """
    Represents a product in the stationery shop's inventory.
    Opening stock is recorded when the product is first added to BizPulse.
    Current stock is calculated from StockMovement records.
    """
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('packet', 'Packet'),
        ('box', 'Box'),
        ('dozen', 'Dozen'),
        ('bundle', 'Bundle'),
        ('ream', 'Ream'),
        ('other', 'Other'),
    ]

    product_code = models.CharField(
        max_length=20, unique=True, editable=False,
        help_text='Auto-generated product code (e.g., PRD-0001)'
    )
    name = models.CharField(max_length=200, verbose_name='Product Name')
    brand = models.CharField(max_length=100, blank=True, default='')
    category = models.CharField(max_length=100, blank=True, default='')
    supplier_name = models.CharField(max_length=200, blank=True, default='')
    unit = models.CharField(
        max_length=20, choices=UNIT_CHOICES, default='piece'
    )
    opening_quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Opening Stock Quantity',
        help_text='Initial stock quantity when the product was first entered'
    )
    purchase_cost_per_unit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Purchase Cost Per Unit (₹)'
    )
    selling_price_per_unit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Selling Price Per Unit (₹)'
    )
    weighted_avg_cost = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text='Weighted average cost per unit, updated on stock additions.'
    )
    minimum_stock_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('5.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Minimum Stock Level',
        help_text='Low-stock alert triggers at or below this quantity'
    )
    stock_entry_date = models.DateField(verbose_name='Stock Entry Date')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['product_code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['category']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'brand', 'unit'],
                name='unique_product_name_brand_unit',
            )
        ]

    def __str__(self):
        if self.brand:
            return f"{self.name} ({self.brand})"
        return self.name

    def save(self, *args, **kwargs):
        if not self.product_code:
            last = Product.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            code = f'PRD-{next_id:04d}'
            while Product.objects.filter(product_code=code).exists():
                next_id += 1
                code = f'PRD-{next_id:04d}'
            self.product_code = code
        # Initialise weighted average cost from opening purchase cost
        if self.weighted_avg_cost == Decimal('0.0000') and self.purchase_cost_per_unit:
            self.weighted_avg_cost = self.purchase_cost_per_unit
        super().save(*args, **kwargs)

    @property
    def current_stock(self):
        """
        Calculate current stock from all stock movements.
        Positive quantities = stock in, Negative quantities = stock out.
        Leverages prefetched cache to prevent N+1 query overhead where available.
        """
        if hasattr(self, '_prefetched_objects_cache') and 'stock_movements' in self._prefetched_objects_cache:
            return sum((m.quantity for m in self.stock_movements.all()), Decimal('0.00'))
        from django.db.models import Sum
        result = self.stock_movements.aggregate(total=Sum('quantity'))
        return result['total'] or Decimal('0.00')

    @property
    def is_low_stock(self):
        """True if current stock is at or below the minimum stock level."""
        return self.current_stock <= self.minimum_stock_level

    @property
    def stock_value(self):
        """Estimated value of current stock on hand using weighted average cost (non-negative asset value)."""
        return max(self.current_stock, Decimal('0.00')) * self.weighted_avg_cost


class StockMovement(models.Model):
    """
    Tracks every stock change for a product. The current stock is the
    sum of all movement quantities for a product.
    Positive quantity = stock in, Negative quantity = stock out.
    """
    MOVEMENT_TYPES = [
        ('OPENING', 'Opening Stock'),
        ('PURCHASE', 'Purchase'),
        ('SALE', 'Sale'),
        ('RETURN_IN', 'Sales Return (Stock In)'),
        ('RETURN_OUT', 'Purchase Return (Stock Out)'),
        ('ADJUSTMENT', 'Stock Adjustment'),
        ('WRITE_OFF', 'Write-off / Damage'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        related_name='stock_movements'
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Positive for stock in, negative for stock out'
    )
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal('0.0000'),
        help_text='Cost per unit at the time of this movement'
    )
    reference_number = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Bill number, invoice number, or adjustment reference'
    )
    date = models.DateField()
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['product', 'movement_type']),
            models.Index(fields=['date']),
            models.Index(fields=['movement_type']),
        ]

    def __str__(self):
        direction = '+' if self.quantity > 0 else ''
        return (
            f"{self.get_movement_type_display()} - "
            f"{self.product.name} ({direction}{self.quantity})"
        )
