from django.contrib import admin
from .models import ExpenseCategory, Expense


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default')
    search_fields = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'description', 'category', 'date', 'amount',
        'payment_status', 'amount_paid', 'outstanding_amount',
    )
    list_filter = ('category', 'payment_status', 'date')
    search_fields = ('description', 'paid_to')
