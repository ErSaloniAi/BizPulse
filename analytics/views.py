import json
import datetime
from django.shortcuts import render, redirect
# Authentication requirement removed for personal use mode
from django.contrib import messages
from django.utils import timezone
from .services import (
    get_date_range,
    calculate_financial_metrics,
    get_comparison_metrics,
    get_daily_sales_chart_data,
    get_monthly_trends_chart_data,
    get_expense_category_chart_data,
    get_top_selling_products,
)
from .reports_service import (
    get_report_dataset,
    export_to_csv,
    export_to_pdf,
)
from inventory.models import Product
from sales.models import Sale


def dashboard(request):
    period = request.GET.get('period', 'this_month')
    custom_start_str = request.GET.get('start_date')
    custom_end_str = request.GET.get('end_date')

    custom_start = None
    custom_end = None
    if period == 'custom' and custom_start_str and custom_end_str:
        try:
            custom_start = datetime.datetime.strptime(custom_start_str, '%Y-%m-%d').date()
            custom_end = datetime.datetime.strptime(custom_end_str, '%Y-%m-%d').date()
        except ValueError:
            period = 'this_month'

    start_date, end_date, period_label, prev_start, prev_end = get_date_range(
        period, custom_start, custom_end
    )

    metrics = calculate_financial_metrics(start_date, end_date)
    growth = get_comparison_metrics(metrics, prev_start, prev_end)

    # Chart datasets
    daily_chart = get_daily_sales_chart_data(start_date, end_date)
    monthly_chart = get_monthly_trends_chart_data()
    expense_chart = get_expense_category_chart_data(start_date, end_date)
    top_products_chart = get_top_selling_products(start_date, end_date, limit=5)

    # Check for empty database state
    has_products = Product.objects.exists()
    has_sales = Sale.objects.exists()
    is_empty_shop = not has_products and not has_sales

    return render(request, 'analytics/dashboard.html', {
        'period': period,
        'period_label': period_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'metrics': metrics,
        'growth': growth,
        'daily_chart_json': json.dumps(daily_chart),
        'monthly_chart_json': json.dumps(monthly_chart),
        'expense_chart_json': json.dumps(expense_chart),
        'top_products_chart_json': json.dumps(top_products_chart),
        'is_empty_shop': is_empty_shop,
    })


def reports_index(request):
    return render(request, 'analytics/reports_index.html')


def report_detail(request, report_type):
    valid_reports = [
        'daily_sales', 'monthly_sales', 'pnl_summary',
        'product_sales', 'expense_category', 'purchases',
        'stock', 'low_stock'
    ]
    if report_type not in valid_reports:
        messages.error(request, "Requested report does not exist.")
        return redirect('analytics:reports_index')

    period = request.GET.get('period', 'this_month')
    custom_start_str = request.GET.get('start_date')
    custom_end_str = request.GET.get('end_date')

    custom_start = None
    custom_end = None
    if period == 'custom' and custom_start_str and custom_end_str:
        try:
            custom_start = datetime.datetime.strptime(custom_start_str, '%Y-%m-%d').date()
            custom_end = datetime.datetime.strptime(custom_end_str, '%Y-%m-%d').date()
        except ValueError:
            period = 'this_month'

    start_date, end_date, period_label, _, _ = get_date_range(
        period, custom_start, custom_end
    )

    title, headers, rows, summary = get_report_dataset(report_type, start_date, end_date)

    return render(request, 'analytics/report_detail.html', {
        'report_type': report_type,
        'title': title,
        'headers': headers,
        'rows': rows,
        'summary': summary,
        'period': period,
        'period_label': period_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
    })


def export_csv_view(request, report_type):
    period = request.GET.get('period', 'this_month')
    custom_start_str = request.GET.get('start_date')
    custom_end_str = request.GET.get('end_date')

    custom_start = None
    custom_end = None
    if period == 'custom' and custom_start_str and custom_end_str:
        try:
            custom_start = datetime.datetime.strptime(custom_start_str, '%Y-%m-%d').date()
            custom_end = datetime.datetime.strptime(custom_end_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    start_date, end_date, _, _, _ = get_date_range(period, custom_start, custom_end)
    title, headers, rows, summary = get_report_dataset(report_type, start_date, end_date)
    return export_to_csv(title, start_date, end_date, headers, rows, summary)


def export_pdf_view(request, report_type):
    period = request.GET.get('period', 'this_month')
    custom_start_str = request.GET.get('start_date')
    custom_end_str = request.GET.get('end_date')

    custom_start = None
    custom_end = None
    if period == 'custom' and custom_start_str and custom_end_str:
        try:
            custom_start = datetime.datetime.strptime(custom_start_str, '%Y-%m-%d').date()
            custom_end = datetime.datetime.strptime(custom_end_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    start_date, end_date, _, _, _ = get_date_range(period, custom_start, custom_end)
    title, headers, rows, summary = get_report_dataset(report_type, start_date, end_date)
    return export_to_pdf(title, start_date, end_date, headers, rows, summary)
