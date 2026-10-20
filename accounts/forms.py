from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import BusinessSetting


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password',
        })
    )


class BusinessSettingForm(forms.ModelForm):
    class Meta:
        model = BusinessSetting
        fields = [
            'shop_name', 'owner_name', 'phone', 'email',
            'address', 'gstin', 'currency_symbol', 'default_low_stock_threshold'
        ]
        widgets = {
            'shop_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Shree Ganesh Stationery'}),
            'owner_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ramesh Sharma'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 9876543210'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. shop@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Shop address'}),
            'gstin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional GSTIN'}),
            'currency_symbol': forms.TextInput(attrs={'class': 'form-control', 'style': 'max-width: 100px;'}),
            'default_low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'style': 'max-width: 120px;'}),
        }
