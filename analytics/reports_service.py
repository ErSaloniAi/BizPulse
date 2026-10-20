import csv
import io
import datetime
from decimal import Decimal
from django.http import HttpResponse
from django.db.models import Sum, Count, F
from django.utils import timezone
from sales.models import Sale, SaleItem
from purchases.models import Purchase, PurchaseItem
from expenses.models import Expense, ExpenseCategory
from inventory.models import Product
from accounts.models import BusinessSetting

# ReportLab imports for professional PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def get_report_dataset(report_type, start_date, end_date):
    """
    Returns title, headers, rows, and summary totals for the requested report.
    """
    if report_type == 'daily_sales':
        title = "Daily Sales Report"
        headers = ["Date", "Bills Count", "Gross Sales (₹)", "Discounts (₹)", "Net Sales (₹)", "Cash Received (₹)", "Outstanding (₹)"]
        rows = []
        curr = start_date
        total_bills = 0
        total_gross = Decimal('0.00')
        total_disc = Decimal('0.00')
        total_net = Decimal('0.00')
        total_rec = Decimal('0.00')
        total_out = Decimal('0.00')

        sales_by_day = Sale.objects.filter(
            sale_date__gte=start_date,
            sale_date__lte=end_date,
            status='confirmed'
        ).values('sale_date').annotate(
            cnt=Count('id'),
            net=Sum('total_amount'),
            rec=Sum('amount_paid'),
            out=Sum('outstanding_amount')
        )
        sales_map = {item['sale_date']: item for item in sales_by_day}

        discounts_by_day = SaleItem.objects.filter(
            sale__sale_date__gte=start_date,
            sale__sale_date__lte=end_date,
            sale__status='confirmed'
        ).values('sale__sale_date').annotate(
            disc=Sum('discount_amount')
        )
        disc_map = {item['sale__sale_date']: (item['disc'] or Decimal('0.00')) for item in discounts_by_day}

        while curr <= end_date:
            if curr in sales_map:
                data = sales_map[curr]
                cnt = data['cnt']
                day_net = data['net'] or Decimal('0.00')
                day_rec = data['rec'] or Decimal('0.00')
                day_out = data['out'] or Decimal('0.00')
                day_disc = disc_map.get(curr, Decimal('0.00'))
                day_gross = day_net + day_disc

                rows.append([
                    curr.strftime('%d-%m-%Y'),
                    cnt,
                    f"{day_gross:.2f}",
                    f"{day_disc:.2f}",
                    f"{day_net:.2f}",
                    f"{day_rec:.2f}",
                    f"{day_out:.2f}",
                ])
                total_bills += cnt
                total_gross += day_gross
                total_disc += day_disc
                total_net += day_net
                total_rec += day_rec
                total_out += day_out

            curr += datetime.timedelta(days=1)

        summary = [
            "Total",
            total_bills,
            f"{total_gross:.2f}",
            f"{total_disc:.2f}",
            f"{total_net:.2f}",
            f"{total_rec:.2f}",
            f"{total_out:.2f}",
        ]
        return title, headers, rows, summary

    elif report_type == 'monthly_sales':
        title = "Monthly Sales Report"
        headers = ["Month", "Bills Count", "Net Sales (₹)", "Cash Received (₹)", "Outstanding (₹)", "Avg Bill Value (₹)"]
        rows = []
        
        # Group sales by month between start_date and end_date
        sales = Sale.objects.filter(
            sale_date__gte=start_date,
            sale_date__lte=end_date,
            status='confirmed'
        ).order_by('sale_date')

        months_map = {}
        for s in sales:
            m_key = s.sale_date.strftime('%Y-%m')
            m_label = s.sale_date.strftime('%B %Y')
            if m_key not in months_map:
                months_map[m_key] = {
                    'label': m_label,
                    'count': 0,
                    'net': Decimal('0.00'),
                    'rec': Decimal('0.00'),
                    'out': Decimal('0.00')
                }
            months_map[m_key]['count'] += 1
            months_map[m_key]['net'] += s.total_amount
            months_map[m_key]['rec'] += s.amount_paid
            months_map[m_key]['out'] += s.outstanding_amount

        total_cnt = 0
        total_net = Decimal('0.00')
        total_rec = Decimal('0.00')
        total_out = Decimal('0.00')

        for m_key in sorted(months_map.keys()):
            data = months_map[m_key]
            avg = data['net'] / data['count'] if data['count'] > 0 else Decimal('0.00')
            rows.append([
                data['label'],
                data['count'],
                f"{data['net']:.2f}",
                f"{data['rec']:.2f}",
                f"{data['out']:.2f}",
                f"{avg:.2f}",
            ])
            total_cnt += data['count']
            total_net += data['net']
            total_rec += data['rec']
            total_out += data['out']

        avg_overall = total_net / total_cnt if total_cnt > 0 else Decimal('0.00')
        summary = ["Total", total_cnt, f"{total_net:.2f}", f"{total_rec:.2f}", f"{total_out:.2f}", f"{avg_overall:.2f}"]
        return title, headers, rows, summary

    elif report_type == 'pnl_summary':
        title = "Profit & Loss Summary Statement"
        headers = ["Financial Statement Item", "Amount (₹)", "Notes / Margin %"]
        
        sales = Sale.objects.filter(sale_date__gte=start_date, sale_date__lte=end_date, status='confirmed')
        net_revenue = sales.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')

        sale_items = SaleItem.objects.filter(sale__in=sales)
        total_discount = sale_items.aggregate(t=Sum('discount_amount'))['t'] or Decimal('0.00')
        gross_sales = net_revenue + total_discount

        cogs = sale_items.aggregate(total_cogs=Sum(F('quantity_sold') * F('historical_cost_per_unit')))['total_cogs'] or Decimal('0.00')
        gross_profit = net_revenue - cogs
        gp_margin = (gross_profit / net_revenue * Decimal('100.0')) if net_revenue > 0 else Decimal('0.00')

        # Operating expenses
        expenses = Expense.objects.filter(date__gte=start_date, date__lte=end_date)
        total_expenses = expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

        net_profit = gross_profit - total_expenses
        np_margin = (net_profit / net_revenue * Decimal('100.0')) if net_revenue > 0 else Decimal('0.00')

        rows = [
            ["Gross Sales (Before Discounts)", f"{gross_sales:.2f}", ""],
            ["Less: Customer Discounts Allowed", f"-{total_discount:.2f}", ""],
            ["Net Sales Revenue", f"{net_revenue:.2f}", "100.0%"],
            ["Less: Cost of Goods Sold (COGS)", f"-{cogs:.2f}", f"{(cogs/net_revenue*100 if net_revenue>0 else 0):.1f}% of revenue"],
            ["GROSS PROFIT", f"{gross_profit:.2f}", f"Margin: {gp_margin:.1f}%"],
            ["Less: Operating Expenses Incurred", "", ""],
        ]

        # Break down top expenses by category
        cat_expenses = expenses.values('category__name').annotate(cat_total=Sum('amount')).order_by('-cat_total')
        for ce in cat_expenses:
            rows.append([f"   • {ce['category__name']}", f"{ce['cat_total']:.2f}", ""])

        rows.extend([
            ["Total Operating Expenses", f"-{total_expenses:.2f}", f"{(total_expenses/net_revenue*100 if net_revenue>0 else 0):.1f}% of revenue"],
            ["NET OPERATING PROFIT (ESTIMATE)", f"{net_profit:.2f}", f"Margin: {np_margin:.1f}%"],
        ])

        summary = None
        return title, headers, rows, summary

    elif report_type == 'product_sales':
        title = "Product-wise Sales & Profitability Report"
        headers = ["Product Name", "Brand", "Unit", "Qty Sold", "Revenue (₹)", "COGS (₹)", "Gross Profit (₹)", "Margin %"]
        rows = []
        
        items = SaleItem.objects.filter(
            sale__sale_date__gte=start_date,
            sale__sale_date__lte=end_date,
            sale__status='confirmed'
        ).select_related('product')

        prod_map = {}
        for it in items:
            p_id = it.product_id
            if p_id not in prod_map:
                prod_map[p_id] = {
                    'name': it.product.name,
                    'brand': it.product.brand or '-',
                    'unit': it.product.get_unit_display(),
                    'qty': Decimal('0.00'),
                    'revenue': Decimal('0.00'),
                    'cogs': Decimal('0.00'),
                }
            prod_map[p_id]['qty'] += it.quantity_sold
            prod_map[p_id]['revenue'] += it.line_total
            prod_map[p_id]['cogs'] += (it.quantity_sold * it.historical_cost_per_unit)

        total_qty = Decimal('0.00')
        total_rev = Decimal('0.00')
        total_cogs = Decimal('0.00')
        total_gp = Decimal('0.00')

        # Sort by revenue descending
        for p_id, d in sorted(prod_map.items(), key=lambda x: x[1]['revenue'], reverse=True):
            gp = d['revenue'] - d['cogs']
            margin = (gp / d['revenue'] * Decimal('100.0')) if d['revenue'] > 0 else Decimal('0.00')
            rows.append([
                d['name'],
                d['brand'],
                d['unit'],
                f"{d['qty']:.2f}",
                f"{d['revenue']:.2f}",
                f"{d['cogs']:.2f}",
                f"{gp:.2f}",
                f"{margin:.1f}%",
            ])
            total_qty += d['qty']
            total_rev += d['revenue']
            total_cogs += d['cogs']
            total_gp += gp

        total_margin = (total_gp / total_rev * Decimal('100.0')) if total_rev > 0 else Decimal('0.00')
        summary = ["Total", "-", "-", f"{total_qty:.2f}", f"{total_rev:.2f}", f"{total_cogs:.2f}", f"{total_gp:.2f}", f"{total_margin:.1f}%"]
        return title, headers, rows, summary

    elif report_type == 'expense_category':
        title = "Expense Category Breakdown Report"
        headers = ["Expense Category", "Entries", "Incurred Amount (₹)", "Amount Paid (₹)", "Outstanding (₹)", "% of Total"]
        rows = []
        
        expenses = Expense.objects.filter(date__gte=start_date, date__lte=end_date)
        total_exp = expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        total_paid = expenses.aggregate(t=Sum('amount_paid'))['t'] or Decimal('0.00')
        total_out = expenses.aggregate(t=Sum('outstanding_amount'))['t'] or Decimal('0.00')
        total_cnt = expenses.count()

        cat_groups = expenses.values('category__name').annotate(
            cnt=Count('id'),
            tot=Sum('amount'),
            paid=Sum('amount_paid'),
            out=Sum('outstanding_amount')
        ).order_by('-tot')

        for cg in cat_groups:
            pct = (cg['tot'] / total_exp * Decimal('100.0')) if total_exp > 0 else Decimal('0.00')
            rows.append([
                cg['category__name'],
                cg['cnt'],
                f"{cg['tot']:.2f}",
                f"{cg['paid']:.2f}",
                f"{cg['out']:.2f}",
                f"{pct:.1f}%",
            ])

        summary = ["Total", total_cnt, f"{total_exp:.2f}", f"{total_paid:.2f}", f"{total_out:.2f}", "100.0%"]
        return title, headers, rows, summary

    elif report_type == 'purchases':
        title = "Purchases Register Report"
        headers = ["Date", "Invoice / Ref #", "Supplier Name", "Total Amount (₹)", "Amount Paid (₹)", "Outstanding (₹)", "Status"]
        rows = []
        
        purchases = Purchase.objects.filter(
            purchase_date__gte=start_date,
            purchase_date__lte=end_date
        ).order_by('-purchase_date')

        total_amount = Decimal('0.00')
        total_paid = Decimal('0.00')
        total_out = Decimal('0.00')

        for p in purchases:
            rows.append([
                p.purchase_date.strftime('%d-%m-%Y'),
                p.invoice_number or f"PO-{p.id}",
                p.supplier_name,
                f"{p.total_amount:.2f}",
                f"{p.amount_paid:.2f}",
                f"{p.outstanding_amount:.2f}",
                p.get_status_display(),
            ])
            if p.status == 'confirmed':
                total_amount += p.total_amount
                total_paid += p.amount_paid
                total_out += p.outstanding_amount

        summary = ["Confirmed Total", "-", "-", f"{total_amount:.2f}", f"{total_paid:.2f}", f"{total_out:.2f}", "-"]
        return title, headers, rows, summary

    elif report_type == 'stock':
        title = "Current Stock Valuation Report"
        headers = ["Code", "Product Name", "Brand", "Unit", "Current Stock", "Min Level", "Unit Cost (₹)", "Stock Value (₹)", "Status"]
        rows = []
        
        products = Product.objects.filter(is_active=True).prefetch_related('stock_movements').order_by('name')
        total_items = 0
        total_value = Decimal('0.00')

        for p in products:
            curr = p.current_stock
            val = max(curr, Decimal('0.00')) * p.weighted_avg_cost
            status_text = "LOW STOCK" if curr <= p.minimum_stock_level else "In Stock"
            if curr <= Decimal('0.00'):
                status_text = "OUT OF STOCK"

            rows.append([
                p.product_code,
                p.name,
                p.brand or '-',
                p.get_unit_display(),
                f"{curr:.2f}",
                f"{p.minimum_stock_level:.2f}",
                f"{p.weighted_avg_cost:.2f}",
                f"{val:.2f}",
                status_text,
            ])
            total_items += 1
            total_value += val

        summary = ["Total Products", f"{total_items} items", "-", "-", "-", "-", "-", f"{total_value:.2f}", "-"]
        return title, headers, rows, summary

    elif report_type == 'low_stock':
        title = "Low-Stock Restocking Report"
        headers = ["Code", "Product Name", "Supplier", "Unit", "Current Stock", "Min Level", "Deficit", "Est. Unit Cost (₹)", "Est. Reorder Cost (₹)"]
        rows = []
        
        products = Product.objects.filter(is_active=True).prefetch_related('stock_movements').order_by('name')
        total_reorder_cost = Decimal('0.00')
        deficit_count = 0

        for p in products:
            curr = p.current_stock
            if curr <= p.minimum_stock_level:
                deficit = max(p.minimum_stock_level - curr, Decimal('0.00'))
                reorder_cost = deficit * p.purchase_cost_per_unit
                rows.append([
                    p.product_code,
                    p.name,
                    p.supplier_name or '-',
                    p.get_unit_display(),
                    f"{curr:.2f}",
                    f"{p.minimum_stock_level:.2f}",
                    f"{deficit:.2f}",
                    f"{p.purchase_cost_per_unit:.2f}",
                    f"{reorder_cost:.2f}",
                ])
                deficit_count += 1
                total_reorder_cost += reorder_cost

        summary = ["Total Items to Reorder", f"{deficit_count} items", "-", "-", "-", "-", "-", "-", f"{total_reorder_cost:.2f}"]
        return title, headers, rows, summary

    else:
        raise ValueError("Invalid report type.")


def export_to_csv(report_title, start_date, end_date, headers, rows, summary=None):
    """
    Streams CSV output for downloading.
    """
    settings = BusinessSetting.objects.first()
    shop_name = settings.shop_name if settings else "BizPulse"

    response = HttpResponse(content_type='text/csv')
    slug_title = report_title.lower().replace(' ', '_').replace('&', 'and')
    response['Content-Disposition'] = f'attachment; filename="{slug_title}_{start_date}_{end_date}.csv"'

    writer = csv.writer(response)
    writer.writerow([shop_name])
    writer.writerow([report_title])
    writer.writerow([f"Period: {start_date} to {end_date}"])
    writer.writerow([])
    writer.writerow(headers)

    for r in rows:
        writer.writerow(r)

    if summary:
        writer.writerow([])
        writer.writerow(summary)

    return response


def export_to_pdf(report_title, start_date, end_date, headers, rows, summary=None):
    """
    Generates a professional PDF report with clean corporate styling using ReportLab.
    """
    settings = BusinessSetting.objects.first()
    shop_name = settings.shop_name if settings else "BizPulse"
    owner_info = f"Proprietor: {settings.owner_name} | Phone: {settings.phone}" if settings and settings.owner_name else ""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1e40af'),
        alignment=1,  # Center
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        alignment=1,
    )
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0f172a'),
        alignment=1,
    )

    elements = []
    elements.append(Paragraph(shop_name.upper(), title_style))
    if owner_info:
        elements.append(Paragraph(owner_info, subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"<b>{report_title}</b>", ParagraphStyle('ReportHeader', parent=meta_style, fontSize=13, leading=16)))
    elements.append(Paragraph(f"Period: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')} | Generated: {timezone.now().strftime('%d-%m-%Y %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=10))

    # Build Table Data
    table_data = [headers]
    if not rows:
        table_data.append(["No records found for the selected period."] + [""] * (len(headers) - 1))
    else:
        for r in rows:
            table_data.append(r)
    if summary:
        table_data.append(summary)

    # Table styling
    t = Table(table_data, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]

    # Set right-alignment for numeric and financial columns
    for c_idx, h in enumerate(headers):
        if any(term in h for term in ['(₹)', 'Count', 'Qty', 'Paid', 'Due', 'Outstanding', 'Amount', 'Revenue', 'Cost', 'Total', 'Deficit', '%', 'Margin']):
            t_style.append(('ALIGN', (c_idx, 0), (c_idx, -1), 'RIGHT'))

    # Alternate row background
    num_rows = len(rows) if rows else 1
    for i in range(1, num_rows + 1):
        bg = colors.HexColor('#f8fafc') if i % 2 == 0 else colors.white
        t_style.append(('BACKGROUND', (0, i), (-1, i), bg))

    # Highlight summary row if present
    if summary:
        t_style.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')))
        t_style.append(('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'))
        t_style.append(('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#0f172a')))

    t.setStyle(TableStyle(t_style))
    elements.append(t)

    # Footer note
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<i>Note: Net Operating Profit Estimate is before taxes, interest, and depreciation. Confidential business report generated by BizPulse.</i>", ParagraphStyle('Foot', parent=subtitle_style, fontSize=7, leading=9)))

    doc.build(elements)
    buffer.seek(0)

    slug_title = report_title.lower().replace(' ', '_').replace('&', 'and')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{slug_title}_{start_date}_{end_date}.pdf"'
    return response
