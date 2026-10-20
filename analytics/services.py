import datetime
from decimal import Decimal
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from sales.models import Sale, SaleItem
from purchases.models import Purchase
from expenses.models import Expense
from inventory.models import Product


def get_date_range(filter_type='this_month', custom_start=None, custom_end=None):
    """
    Returns (start_date, end_date, label, prev_start, prev_end) based on filter_type.
    """
    today = timezone.localdate()

    if filter_type == 'today':
        start_date = today
        end_date = today
        label = f"Today ({today.strftime('%d %b %Y')})"
        prev_start = today - datetime.timedelta(days=1)
        prev_end = today - datetime.timedelta(days=1)

    elif filter_type == 'last_7_days':
        start_date = today - datetime.timedelta(days=6)
        end_date = today
        label = f"Last 7 Days ({start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')})"
        prev_start = start_date - datetime.timedelta(days=7)
        prev_end = start_date - datetime.timedelta(days=1)

    elif filter_type == 'previous_month':
        # First day of this month
        first_this_month = today.replace(day=1)
        # Last day of previous month
        prev_month_end = first_this_month - datetime.timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        start_date = prev_month_start
        end_date = prev_month_end
        label = f"Previous Month ({start_date.strftime('%B %Y')})"

        # Comparison period: month before previous
        month_before_end = prev_month_start - datetime.timedelta(days=1)
        prev_start = month_before_end.replace(day=1)
        prev_end = month_before_end

    elif filter_type == 'custom' and custom_start and custom_end:
        if custom_start > custom_end:
            custom_start, custom_end = custom_end, custom_start
        start_date = custom_start
        end_date = custom_end
        label = f"Custom: {start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"
        duration = (end_date - start_date).days + 1
        prev_end = start_date - datetime.timedelta(days=1)
        prev_start = prev_end - datetime.timedelta(days=duration - 1)

    elif filter_type == 'all_time':
        candidate_dates = []
        earliest_sale = Sale.objects.filter(status='confirmed').order_by('sale_date').values_list('sale_date', flat=True).first()
        if earliest_sale:
            candidate_dates.append(earliest_sale)
        earliest_purchase = Purchase.objects.filter(status='confirmed').order_by('purchase_date').values_list('purchase_date', flat=True).first()
        if earliest_purchase:
            candidate_dates.append(earliest_purchase)
        earliest_expense = Expense.objects.order_by('date').values_list('date', flat=True).first()
        if earliest_expense:
            candidate_dates.append(earliest_expense)
        earliest_prod = Product.objects.order_by('stock_entry_date').values_list('stock_entry_date', flat=True).first()
        if earliest_prod:
            candidate_dates.append(earliest_prod)

        start_date = min(candidate_dates) if candidate_dates else today.replace(day=1)
        end_date = today
        label = "All Time"
        prev_start = None
        prev_end = None

    else:  # Default: this_month
        filter_type = 'this_month'
        start_date = today.replace(day=1)
        end_date = today
        label = f"This Month ({start_date.strftime('%B %Y')})"

        # Previous month for like-for-like MTD comparison
        last_day_prev_month = start_date - datetime.timedelta(days=1)
        prev_start = last_day_prev_month.replace(day=1)
        prev_day = min(today.day, last_day_prev_month.day)
        prev_end = prev_start.replace(day=prev_day)

    return start_date, end_date, label, prev_start, prev_end


def calculate_financial_metrics(start_date, end_date):
    """
    Computes all core financial, operational, and cash flow metrics for the given period.
    """
    # 1. Sales & Revenue
    sales_qs = Sale.objects.filter(
        sale_date__gte=start_date,
        sale_date__lte=end_date,
        status='confirmed'
    )
    total_sales_revenue = sales_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    bill_count = sales_qs.count()
    avg_bill_value = (total_sales_revenue / bill_count) if bill_count > 0 else Decimal('0.00')

    # Cash Inflow from sales
    cash_inflow = sales_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    sales_receivables = sales_qs.aggregate(total=Sum('outstanding_amount'))['total'] or Decimal('0.00')

    # 2. Cost of Goods Sold (COGS) via direct database aggregation
    sale_items_qs = SaleItem.objects.filter(
        sale__sale_date__gte=start_date,
        sale__sale_date__lte=end_date,
        sale__status='confirmed'
    )
    cogs_agg = sale_items_qs.aggregate(
        total_cogs=Sum(F('quantity_sold') * F('historical_cost_per_unit'))
    )['total_cogs']
    cogs = cogs_agg or Decimal('0.00')

    # 3. Gross Profit & Margin
    gross_profit = total_sales_revenue - cogs
    gross_profit_margin = (
        (gross_profit / total_sales_revenue * Decimal('100.0'))
        if total_sales_revenue > Decimal('0.00')
        else Decimal('0.00')
    )

    # 4. Operating Expenses (incurred)
    expenses_qs = Expense.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    total_operating_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses_cash_paid = expenses_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    expenses_outstanding = expenses_qs.aggregate(total=Sum('outstanding_amount'))['total'] or Decimal('0.00')

    # 5. Purchases in period
    purchases_qs = Purchase.objects.filter(
        purchase_date__gte=start_date,
        purchase_date__lte=end_date,
        status='confirmed'
    )
    total_purchases = purchases_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    purchases_cash_paid = purchases_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    purchases_outstanding = purchases_qs.aggregate(total=Sum('outstanding_amount'))['total'] or Decimal('0.00')

    # 6. Net Operating Profit Estimate
    net_operating_profit = gross_profit - total_operating_expenses
    net_profit_margin = (
        (net_operating_profit / total_sales_revenue * Decimal('100.0'))
        if total_sales_revenue > Decimal('0.00')
        else Decimal('0.00')
    )

    # 7. Cash Flow (Realized Cash vs Incurred Profit)
    total_cash_outflow = purchases_cash_paid + expenses_cash_paid
    net_cash_flow = cash_inflow - total_cash_outflow

    # 8. Current Stock Valuation & Low Stock (strictly non-negative asset valuation)
    all_products = Product.objects.filter(is_active=True).prefetch_related('stock_movements')
    current_stock_value = Decimal('0.00')
    low_stock_products = []
    for p in all_products:
        curr = p.current_stock
        current_stock_value += (max(curr, Decimal('0.00')) * p.weighted_avg_cost)
        if curr <= p.minimum_stock_level:
            low_stock_products.append({
                'product': p,
                'current_stock': curr,
                'minimum_stock': p.minimum_stock_level,
                'deficit': max(p.minimum_stock_level - curr, Decimal('0.00')),
            })

    return {
        'total_sales_revenue': total_sales_revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'gross_profit_margin': round(gross_profit_margin, 2),
        'total_operating_expenses': total_operating_expenses,
        'net_operating_profit': net_operating_profit,
        'net_profit_margin': round(net_profit_margin, 2),
        'total_purchases': total_purchases,
        'bill_count': bill_count,
        'avg_bill_value': round(avg_bill_value, 2),
        'cash_inflow': cash_inflow,
        'total_cash_outflow': total_cash_outflow,
        'net_cash_flow': net_cash_flow,
        'sales_receivables': sales_receivables,
        'payables': purchases_outstanding + expenses_outstanding,
        'current_stock_value': round(current_stock_value, 2),
        'low_stock_count': len(low_stock_products),
        'low_stock_products': low_stock_products[:10],
    }


def get_comparison_metrics(curr_metrics, prev_start, prev_end):
    """
    Computes percentage growth of sales and profit compared to previous period.
    """
    if not prev_start or not prev_end:
        return {'sales_growth': None, 'profit_growth': None}

    prev_metrics = calculate_financial_metrics(prev_start, prev_end)
    prev_rev = prev_metrics['total_sales_revenue']
    curr_rev = curr_metrics['total_sales_revenue']

    if prev_rev > Decimal('0.00'):
        sales_growth = round(((curr_rev - prev_rev) / prev_rev) * Decimal('100.0'), 1)
    else:
        sales_growth = None

    prev_profit = prev_metrics['net_operating_profit']
    curr_profit = curr_metrics['net_operating_profit']

    if prev_profit != Decimal('0.00'):
        profit_growth = round(((curr_profit - prev_profit) / abs(prev_profit)) * Decimal('100.0'), 1)
    else:
        profit_growth = None

    return {
        'sales_growth': sales_growth,
        'profit_growth': profit_growth,
        'prev_revenue': prev_rev,
        'prev_profit': prev_profit,
    }


def get_daily_sales_chart_data(start_date, end_date):
    """
    Returns daily sales revenue and bill count for Chart.js.
    Uses a single database query to avoid N+1 query overhead.
    """
    day_sales_qs = Sale.objects.filter(
        sale_date__gte=start_date,
        sale_date__lte=end_date,
        status='confirmed'
    ).values('sale_date').annotate(
        total_rev=Sum('total_amount'),
        cnt=Count('id')
    )
    sales_map = {item['sale_date']: item for item in day_sales_qs}

    labels = []
    revenues = []
    bills = []

    curr = start_date
    while curr <= end_date:
        labels.append(curr.strftime('%d %b'))
        day_data = sales_map.get(curr)
        rev = day_data['total_rev'] if day_data else Decimal('0.00')
        cnt = day_data['cnt'] if day_data else 0

        revenues.append(round(float(rev), 2))
        bills.append(cnt)
        curr += datetime.timedelta(days=1)

    return {
        'labels': labels,
        'revenues': revenues,
        'bills': bills,
    }


def get_monthly_trends_chart_data():
    """
    Returns last 6 months revenue, gross profit, and expenses trend for Chart.js.
    """
    today = timezone.localdate()
    months = []
    revenues = []
    profits = []
    expenses = []

    # Get last 6 months
    for i in range(5, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        first_day = datetime.date(year, month, 1)
        if month == 12:
            last_day = datetime.date(year, 12, 31)
        else:
            last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        m_metrics = calculate_financial_metrics(first_day, last_day)

        months.append(first_day.strftime('%b %Y'))
        revenues.append(round(float(m_metrics['total_sales_revenue']), 2))
        profits.append(round(float(m_metrics['net_operating_profit']), 2))
        expenses.append(round(float(m_metrics['total_operating_expenses']), 2))

    return {
        'months': months,
        'revenues': revenues,
        'profits': profits,
        'expenses': expenses,
    }


def get_expense_category_chart_data(start_date, end_date):
    """
    Returns expense category breakdown for doughnut chart.
    """
    expenses = Expense.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).values('category__name').annotate(total=Sum('amount')).order_by('-total')

    labels = []
    amounts = []
    for exp in expenses:
        labels.append(exp['category__name'])
        amounts.append(round(float(exp['total']), 2))

    return {
        'labels': labels,
        'amounts': amounts,
    }


def get_top_selling_products(start_date, end_date, limit=5):
    """
    Returns top selling products by quantity and revenue.
    """
    items = SaleItem.objects.filter(
        sale__sale_date__gte=start_date,
        sale__sale_date__lte=end_date,
        sale__status='confirmed'
    ).values('product__name', 'product__brand', 'product__unit').annotate(
        total_qty=Sum('quantity_sold'),
        total_revenue=Sum('line_total')
    ).order_by('-total_qty')[:limit]

    labels = []
    quantities = []
    revenues = []
    for item in items:
        brand_str = f" ({item['product__brand']})" if item['product__brand'] else ""
        labels.append(f"{item['product__name']}{brand_str}")
        quantities.append(round(float(item['total_qty']), 2))
        revenues.append(round(float(item['total_revenue']), 2))

    return {
        'labels': labels,
        'quantities': quantities,
        'revenues': revenues,
    }
