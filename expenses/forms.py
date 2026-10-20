from decimal import Decimal
from django import forms
from django.utils import timezone
from .models import Expense, ExpenseCategory


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'category', 'date', 'description', 'amount',
            'payment_status', 'amount_paid', 'payment_method',
            'paid_to', 'receipt_reference', 'notes'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Shop monthly rent for October'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'paid_to': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Landlord Sharma ji'}),
            'receipt_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Bill / Voucher #102'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional remarks'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'date' not in self.initial:
            self.fields['date'].initial = timezone.localdate()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= Decimal('0.00'):
            raise forms.ValidationError("Expense amount must be greater than zero.")
        return amount

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get('amount_paid')
        if amount_paid is not None and amount_paid < Decimal('0.00'):
            raise forms.ValidationError("Amount paid cannot be negative.")
        return amount_paid

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount') or Decimal('0.00')
        amount_paid = cleaned_data.get('amount_paid') or Decimal('0.00')
        payment_status = cleaned_data.get('payment_status')

        if payment_status == 'paid' and amount_paid == Decimal('0.00') and amount > Decimal('0.00'):
            # Convenience: if status is set to 'Paid', assume full amount was paid
            cleaned_data['amount_paid'] = amount
        elif payment_status == 'unpaid':
            cleaned_data['amount_paid'] = Decimal('0.00')
        elif amount_paid > amount:
            self.add_error('amount_paid', "Amount paid cannot exceed total expense amount.")

        return cleaned_data


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Refreshments & Tea'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Category name cannot be empty.")
        if ExpenseCategory.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A category with this name already exists.")
        return name
