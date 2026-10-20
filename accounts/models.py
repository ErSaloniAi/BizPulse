from django.db import models


class BusinessSetting(models.Model):
    """
    Stores the shop's business information.
    Only one row should exist — accessed via BusinessSetting.objects.first().
    """
    shop_name = models.CharField(max_length=200, default='My Stationery Shop')
    owner_name = models.CharField(max_length=200, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')
    gstin = models.CharField(
        max_length=15, blank=True, default='',
        verbose_name='GSTIN',
        help_text='Goods and Services Tax Identification Number'
    )
    currency_symbol = models.CharField(max_length=5, default='₹')
    default_low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text='Default minimum stock level for new products'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Business Setting'
        verbose_name_plural = 'Business Settings'

    def __str__(self):
        return self.shop_name

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and BusinessSetting.objects.exists():
            existing = BusinessSetting.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
