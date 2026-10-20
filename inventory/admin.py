from django.contrib import admin
from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'product_code', 'name', 'brand', 'category',
        'unit', 'selling_price_per_unit', 'purchase_cost_per_unit',
        'minimum_stock_level', 'is_active',
    )
    list_filter = ('category', 'unit', 'is_active')
    search_fields = ('name', 'brand', 'product_code')
    readonly_fields = ('product_code', 'weighted_avg_cost')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'movement_type', 'quantity',
        'unit_cost', 'date', 'reference_number',
    )
    list_filter = ('movement_type', 'date')
    search_fields = ('product__name', 'reference_number')
    readonly_fields = ('created_at',)
