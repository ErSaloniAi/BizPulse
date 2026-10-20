from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    readonly_fields = ('line_total', 'historical_cost_per_unit')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'bill_number', 'sale_date', 'customer_name',
        'total_amount', 'payment_status', 'status',
    )
    list_filter = ('status', 'payment_status', 'sale_date')
    search_fields = ('bill_number', 'customer_name')
    inlines = [SaleItemInline]
    readonly_fields = ('total_amount', 'outstanding_amount')
