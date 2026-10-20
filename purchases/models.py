from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal, ROUND_HALF_UP
from inventory.models import Product


class Purchase(models.Model):
    """
    Represents a stock purchase from a supplier.
    Contains invoice-level information. Individual products purchased
    are tracked in PurchaseItem.
    """
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('unpaid', 'Unpaid'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('', '--------'),
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('bank', 'Bank Transfer'),
        ('credit', 'Credit'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('voided', 'Voided'),
    ]

    invoice_number = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Invoice / Reference Number',
        help_text='Supplier invoice or bill reference number'
    )
    purchase_date = models.DateField(verbose_name='Purchase Date')
    supplier_name = models.CharField(
        max_length=200, verbose_name='Supplier Name'
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Total Purchase Amount (₹)'
    )
    payment_status = models.CharField(
        max_length=10, choices=PAYMENT_STATUS_CHOICES, default='paid'
    )
    amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Amount Paid (₹)'
    )
    outstanding_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Outstanding Amount (₹)'
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_METHOD_CHOICES,
        default='cash', blank=True
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='confirmed'
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_date', '-created_at']
        indexes = [
            models.Index(fields=['purchase_date']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['supplier_name']),
        ]

    def __str__(self):
        ref = self.invoice_number or 'No Ref'
        return f"Purchase [{ref}] — {self.purchase_date}"

    def calculate_total(self):
        """Recalculate total from line items and update outstanding."""
        total = self.items.aggregate(
            total=models.Sum('line_total')
        )['total'] or Decimal('0.00')
        self.total_amount = total
        self.outstanding_amount = max(
            self.total_amount - self.amount_paid, Decimal('0.00')
        )
        return total

    def save(self, *args, **kwargs):
        # Auto-calculate outstanding and enforce payment status synchronization
        self.outstanding_amount = max(
            self.total_amount - self.amount_paid, Decimal('0.00')
        )
        if self.amount_paid >= self.total_amount and self.total_amount > Decimal('0.00'):
            self.payment_status = 'paid'
            self.outstanding_amount = Decimal('0.00')
        elif self.amount_paid > Decimal('0.00'):
            self.payment_status = 'partial'
        else:
            self.payment_status = 'unpaid'
        super().save(*args, **kwargs)


class PurchaseItem(models.Model):
    """
    Represents a single product line in a purchase invoice.
    Records the actual purchase cost for historical accuracy.
    """
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='purchase_items'
    )
    quantity_purchased = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Quantity'
    )
    purchase_cost_per_unit = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Cost Per Unit (₹)'
    )
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Total (₹)'
    )

    class Meta:
        indexes = [
            models.Index(fields=['purchase', 'product']),
        ]

    def __str__(self):
        return f"{self.product.name} × {self.quantity_purchased}"

    def calculate_line_total(self):
        """Line Total = Quantity × Cost Per Unit with exact 2-decimal rounding."""
        total = self.quantity_purchased * self.purchase_cost_per_unit
        self.line_total = max(total, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return self.line_total

    def save(self, *args, **kwargs):
        self.calculate_line_total()
        super().save(*args, **kwargs)
