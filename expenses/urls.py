from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expense_list, name='expense_list'),
    path('new/', views.expense_create, name='expense_create'),
    path('upload-csv/', views.expense_csv_upload, name='upload_csv'),
    path('sample-csv/', views.expense_csv_sample, name='sample_csv'),
    path('categories/', views.category_list, name='category_list'),
    path('<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('<int:pk>/delete/', views.expense_delete, name='expense_delete'),
]
