from django import forms
from django.utils import timezone
from .models import Sale


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = [
            'bill_number', 'sale_date', 'customer_name',
            'payment_status', 'amount_paid', 'payment_method', 'notes'
        ]
        widgets = {
            'bill_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BILL-0001'}),
            'sale_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. M/s Adarsh High School or Cash'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional remarks or payment details'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'sale_date' not in self.initial:
            self.fields['sale_date'].initial = timezone.localdate()
