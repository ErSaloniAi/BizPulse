from django.contrib import admin
from .models import BusinessSetting


@admin.register(BusinessSetting)
class BusinessSettingAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'owner_name', 'phone', 'gstin')
