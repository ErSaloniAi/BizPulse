from django.contrib import admin
from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    readonly_fields = ('line_total',)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'purchase_date', 'supplier_name',
        'total_amount', 'payment_status', 'status',
    )
    list_filter = ('status', 'payment_status', 'purchase_date')
    search_fields = ('invoice_number', 'supplier_name')
    inlines = [PurchaseItemInline]
    readonly_fields = ('total_amount', 'outstanding_amount')
