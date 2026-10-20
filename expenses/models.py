from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class ExpenseCategory(models.Model):
    """
    Predefined and user-added operating expense categories.
    Default categories are seeded via a data migration.
    """
    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(
        default=False,
        help_text='True for system-seeded categories'
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    Records a single operating expense.
    One table for all expense categories — not separate tables.
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
        ('other', 'Other'),
    ]

    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT,
        related_name='expenses',
        verbose_name='Expense Category'
    )
    date = models.DateField(verbose_name='Expense Date')
    description = models.CharField(
        max_length=300, verbose_name='Expense Description',
        help_text='Brief description of the expense'
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Amount (₹)'
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
    paid_to = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Paid To'
    )
    receipt_reference = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Receipt / Bill Reference'
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['category']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f"{self.description} — ₹{self.amount}"

    def save(self, *args, **kwargs):
        # Auto-calculate outstanding
        self.outstanding_amount = max(
            self.amount - self.amount_paid, Decimal('0.00')
        )
        # Auto-set payment status based on amounts
        if self.amount_paid >= self.amount:
            self.payment_status = 'paid'
            self.outstanding_amount = Decimal('0.00')
        elif self.amount_paid > Decimal('0.00'):
            self.payment_status = 'partial'
        else:
            self.payment_status = 'unpaid'
        super().save(*args, **kwargs)
