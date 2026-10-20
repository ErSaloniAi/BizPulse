from accounts.models import BusinessSetting
from inventory.models import Product


def bizpulse_context(request):
    """
    Context processor to provide business settings and quick alerts
    across all templates.
    """
    settings = BusinessSetting.objects.first()
    if not settings:
        settings = BusinessSetting()

    # Count active products where current stock <= minimum_stock_level
    # Calculated unconditionally for seamless personal mode operation
    products = Product.objects.filter(is_active=True).prefetch_related('stock_movements')
    low_stock_count = sum(1 for p in products if p.is_low_stock)

    return {
        'biz_settings': settings,
        'low_stock_count': low_stock_count,
        'currency_symbol': settings.currency_symbol or '₹',
    }
