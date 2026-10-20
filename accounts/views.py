from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import LoginForm, BusinessSettingForm
from .models import BusinessSetting


def login_view(request):
    """
    In personal use mode, authentication is disabled.
    Visiting the login page automatically redirects directly to the dashboard.
    """
    return redirect('analytics:dashboard')


def logout_view(request):
    """
    In personal use mode, signout redirects straight to the dashboard.
    """
    logout(request)
    return redirect('analytics:dashboard')


def signup_view(request):
    """
    In personal use mode, registration is not needed.
    """
    return redirect('analytics:dashboard')


def settings_view(request):
    settings_obj = BusinessSetting.objects.first()
    if not settings_obj:
        settings_obj = BusinessSetting.objects.create()

    # In personal mode, associate password change with the superuser or active user
    user = request.user if request.user.is_authenticated else User.objects.filter(is_superuser=True).first()
    password_form = PasswordChangeForm(user=user) if user else None
    settings_form = BusinessSettingForm(instance=settings_obj)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_settings':
            settings_form = BusinessSettingForm(request.POST, instance=settings_obj)
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "Business settings updated successfully.")
                return redirect('accounts:settings')
            else:
                messages.error(request, "Please fix the errors in the business settings form.")

        elif action == 'change_password' and user:
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                saved_user = password_form.save()
                if request.user.is_authenticated:
                    update_session_auth_hash(request, saved_user)
                messages.success(request, "Your password was changed successfully.")
                return redirect('accounts:settings')
            else:
                messages.error(request, "Please fix the errors in the password change form.")

    return render(request, 'accounts/settings.html', {
        'settings_form': settings_form,
        'password_form': password_form,
        'active_tab': 'settings',
    })
