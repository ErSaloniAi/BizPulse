from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('register/', views.signup_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('signin/', views.login_view, name='signin'),
    path('logout/', views.logout_view, name='logout'),
    path('signout/', views.logout_view, name='signout'),
    path('settings/', views.settings_view, name='settings'),
]
