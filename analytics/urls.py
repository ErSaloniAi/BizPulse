from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('reports/', views.reports_index, name='reports_index'),
    path('reports/<str:report_type>/', views.report_detail, name='report_detail'),
    path('reports/<str:report_type>/csv/', views.export_csv_view, name='export_csv'),
    path('reports/<str:report_type>/pdf/', views.export_pdf_view, name='export_pdf'),
]
