import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
# Authentication requirement removed for personal use mode
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Sale, SaleItem
from .forms import SaleForm
from .services import generate_next_bill_number, create_sale_bill, void_sale_bill
from inventory.models import Product


def sale_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'confirmed').strip()
    payment_filter = request.GET.get('payment_status', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    sales = Sale.objects.all().order_by('-sale_date', '-created_at')

    if status_filter != 'all':
        sales = sales.filter(status=status_filter)

    if payment_filter:
        sales = sales.filter(payment_status=payment_filter)

    if start_date:
        sales = sales.filter(sale_date__gte=start_date)

    if end_date:
        sales = sales.filter(sale_date__lte=end_date)

    if query:
        sales = sales.filter(
            Q(bill_number__icontains=query) |
            Q(customer_name__icontains=query)
        )

    # Summary metrics for current filtered query
    valid_sales = sales.filter(status='confirmed')
    total_sales_revenue = valid_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_amount_received = valid_sales.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_outstanding = valid_sales.aggregate(total=Sum('outstanding_amount'))['total'] or Decimal('0.00')

    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'sales/sale_list.html', {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'start_date': start_date,
        'end_date': end_date,
        'total_sales_revenue': total_sales_revenue,
        'total_amount_received': total_amount_received,
        'total_outstanding': total_outstanding,
    })


def sale_create(request):
    products = Product.objects.filter(is_active=True).order_by('name')
    products_json = []
    for p in products:
        products_json.append({
            'id': p.id,
            'name': p.name,
            'brand': p.brand,
            'code': p.product_code,
            'unit': p.get_unit_display(),
            'price': str(p.selling_price_per_unit),
            'stock': str(p.current_stock),
        })

    if request.method == 'POST':
        form = SaleForm(request.POST)
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('price[]')
        discounts = request.POST.getlist('discount[]')

        items_data = []
        for i in range(len(product_ids)):
            if product_ids[i]:
                items_data.append({
                    'product_id': product_ids[i],
                    'quantity': quantities[i] if i < len(quantities) else '1',
                    'actual_selling_price_per_unit': prices[i] if i < len(prices) else '0',
                    'discount_amount': discounts[i] if i < len(discounts) else '0',
                })

        sale_data = {
            'bill_number': request.POST.get('bill_number', '').strip(),
            'sale_date': request.POST.get('sale_date') or timezone.localdate(),
            'customer_name': request.POST.get('customer_name', '').strip(),
            'payment_status': request.POST.get('payment_status', 'paid'),
            'amount_paid': request.POST.get('amount_paid', '0'),
            'payment_method': request.POST.get('payment_method', 'cash'),
            'notes': request.POST.get('notes', '').strip(),
        }

        try:
            sale = create_sale_bill(sale_data, items_data)
            messages.success(request, f"Bill #{sale.bill_number} for ₹{sale.total_amount} was successfully created.")
            return redirect('sales:sale_detail', pk=sale.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Error saving bill: {str(e)}")

    else:
        initial_bill_num = generate_next_bill_number()
        form = SaleForm(initial={'bill_number': initial_bill_num, 'sale_date': timezone.localdate()})

    return render(request, 'sales/sale_form.html', {
        'form': form,
        'products': products,
        'products_json': json.dumps(products_json),
    })


def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    items = sale.items.select_related('product').all()

    # Calculate COGS and Gross profit for this specific bill
    cogs = sum(item.quantity_sold * item.historical_cost_per_unit for item in items)
    gross_profit = sale.total_amount - cogs if sale.status == 'confirmed' else Decimal('0.00')

    return render(request, 'sales/sale_detail.html', {
        'sale': sale,
        'items': items,
        'cogs': cogs,
        'gross_profit': gross_profit,
    })


def sale_void(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            void_sale_bill(sale, reason=reason)
            messages.warning(request, f"Bill #{sale.bill_number} has been voided. Stock was restored.")
            return redirect('sales:sale_detail', pk=sale.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Error voiding bill: {str(e)}")

    return render(request, 'sales/sale_void_confirm.html', {'sale': sale})


def sale_csv_upload(request):
    from .csv_services import import_sales_from_csv
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'sales/upload_csv.html')

        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a file ending with .csv")
            return render(request, 'sales/upload_csv.html')

        try:
            bills, items, errors = import_sales_from_csv(csv_file)
            if errors:
                for err in errors[:5]:
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"...and {len(errors) - 5} more error(s).")
            if bills > 0:
                messages.success(request, f"Sales CSV Import complete: {bills} bill(s) recorded with {items} items sold.")
                return redirect('sales:sale_list')
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")

    return render(request, 'sales/upload_csv.html')


def sale_csv_sample(request):
    from .csv_services import get_sales_sample_csv
    return get_sales_sample_csv()

