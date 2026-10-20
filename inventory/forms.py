from decimal import Decimal
from django import forms
from django.utils import timezone
from .models import Product, StockMovement
from .services import check_duplicate_product


class ProductForm(forms.ModelForm):
    allow_duplicate = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
        initial=False
    )

    class Meta:
        model = Product
        fields = [
            'name', 'brand', 'category', 'supplier_name', 'unit',
            'opening_quantity', 'purchase_cost_per_unit', 'selling_price_per_unit',
            'minimum_stock_level', 'stock_entry_date',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Classmate Notebook 200 Pages'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ITC Classmate'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Notebooks & Registers', 'list': 'categories-datalist'}),
            'supplier_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Raj Stationery Mart'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'opening_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'purchase_cost_per_unit': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'selling_price_per_unit': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'minimum_stock_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'stock_entry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'stock_entry_date' not in self.initial:
            self.fields['stock_entry_date'].initial = timezone.localdate()

        # If editing an existing product, make opening quantity read-only to preserve baseline
        if self.instance.pk:
            self.fields['opening_quantity'].disabled = True
            self.fields['opening_quantity'].help_text = "Opening stock baseline cannot be changed directly. Use 'Adjust Stock' for corrections."

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Product name is required.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        brand = cleaned_data.get('brand', '')
        unit = cleaned_data.get('unit', 'piece')
        allow_duplicate = cleaned_data.get('allow_duplicate', False)

        if name:
            existing = check_duplicate_product(
                name=name,
                brand=brand,
                unit=unit,
                exclude_pk=self.instance.pk
            )
            if existing and not allow_duplicate:
                self.duplicate_found = existing
                raise forms.ValidationError(
                    f"A product with name '{name}', brand '{brand or 'None'}', and unit '{unit}' already exists (Code: {existing.product_code}). "
                    f"If you intend to add this similar item anyway, check 'Confirm and save duplicate' below."
                )

        cost = cleaned_data.get('purchase_cost_per_unit')
        price = cleaned_data.get('selling_price_per_unit')
        if cost is not None and cost < Decimal('0.00'):
            self.add_error('purchase_cost_per_unit', "Purchase cost cannot be negative.")
        if price is not None and price < Decimal('0.00'):
            self.add_error('selling_price_per_unit', "Selling price cannot be negative.")

        return cleaned_data


class StockAdjustmentForm(forms.Form):
    ADJUSTMENT_CHOICES = [
        ('ADD', 'Add Stock (+) — Found Stock / Correction'),
        ('SUBTRACT', 'Deduct Stock (-) — Damaged / Expired / Lost'),
    ]

    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.DecimalField(
        min_value=Decimal('0.01'),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    reason = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Water damage, Physical stock audit variance'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional remarks'})
    )
