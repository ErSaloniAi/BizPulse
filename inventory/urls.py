from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.product_create, name='product_create'),
    path('upload-csv/', views.product_csv_upload, name='upload_csv'),
    path('sample-csv/', views.product_csv_sample, name='sample_csv'),
    path('low-stock/', views.low_stock_list, name='low_stock_list'),
    path('api/lookup/', views.product_api_lookup, name='product_api_lookup'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/adjust/', views.stock_adjustment, name='stock_adjustment'),
]
