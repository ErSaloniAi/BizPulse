from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal, ROUND_HALF_UP
from inventory.models import Product


class Sale(models.Model):
    """
    Represents a sales bill from the shop's bill book.
    Contains bill-level information. Individual products sold
    are tracked in SaleItem.
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

    bill_number = models.CharField(
        max_length=50, unique=True,
        verbose_name='Bill Number',
        help_text='Unique bill number from the bill book'
    )
    sale_date = models.DateField(verbose_name='Sale Date')
    customer_name = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Customer / Business Name (M/s)',
        help_text='Optional — name from the bill book'
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Total Bill Amount (₹)'
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
        ordering = ['-sale_date', '-created_at']
        indexes = [
            models.Index(fields=['sale_date']),
            models.Index(fields=['bill_number']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f"Bill #{self.bill_number} — {self.sale_date}"

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


class SaleItem(models.Model):
    """
    Represents a single product line in a sales bill.
    Captures actual selling price and historical cost at time of sale.
    """
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='sale_items'
    )
    quantity_sold = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Quantity'
    )
    actual_selling_price_per_unit = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Selling Price Per Unit (₹)',
        help_text='Actual rate charged to the customer'
    )
    historical_cost_per_unit = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal('0.0000'),
        help_text='Weighted average cost at time of sale, used for COGS'
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Discount (₹)'
    )
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Amount (₹)'
    )

    class Meta:
        indexes = [
            models.Index(fields=['sale', 'product']),
        ]

    def __str__(self):
        return f"{self.product.name} × {self.quantity_sold}"

    def calculate_line_total(self):
        """Line Total = (Quantity × Price) - Discount with exact 2-decimal rounding."""
        subtotal = (self.quantity_sold * self.actual_selling_price_per_unit) - self.discount_amount
        self.line_total = max(subtotal, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return self.line_total

    def save(self, *args, **kwargs):
        self.calculate_line_total()
        super().save(*args, **kwargs)
