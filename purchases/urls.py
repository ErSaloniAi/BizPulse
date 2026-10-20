from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='purchase_list'),
    path('new/', views.purchase_create, name='purchase_create'),
    path('upload-csv/', views.purchase_csv_upload, name='upload_csv'),
    path('sample-csv/', views.purchase_csv_sample, name='sample_csv'),
    path('<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('<int:pk>/void/', views.purchase_void, name='purchase_void'),
]
