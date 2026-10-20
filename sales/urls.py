from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('new/', views.sale_create, name='sale_create'),
    path('upload-csv/', views.sale_csv_upload, name='upload_csv'),
    path('sample-csv/', views.sale_csv_sample, name='sample_csv'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/void/', views.sale_void, name='sale_void'),
]
