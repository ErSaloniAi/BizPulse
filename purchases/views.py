import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
# Authentication requirement removed for personal use mode
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Purchase, PurchaseItem
from .forms import PurchaseForm
from .services import create_purchase_order, void_purchase_order
from inventory.models import Product


def purchase_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'confirmed').strip()
    payment_filter = request.GET.get('payment_status', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    purchases = Purchase.objects.all().order_by('-purchase_date', '-created_at')

    if status_filter != 'all':
        purchases = purchases.filter(status=status_filter)

    if payment_filter:
        purchases = purchases.filter(payment_status=payment_filter)

    if start_date:
        purchases = purchases.filter(purchase_date__gte=start_date)

    if end_date:
        purchases = purchases.filter(purchase_date__lte=end_date)

    if query:
        purchases = purchases.filter(
            Q(invoice_number__icontains=query) |
            Q(supplier_name__icontains=query)
        )

    valid_purchases = purchases.filter(status='confirmed')
    total_purchase_amount = valid_purchases.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_paid = valid_purchases.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_outstanding = valid_purchases.aggregate(total=Sum('outstanding_amount'))['total'] or Decimal('0.00')

    paginator = Paginator(purchases, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'purchases/purchase_list.html', {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'start_date': start_date,
        'end_date': end_date,
        'total_purchase_amount': total_purchase_amount,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
    })


def purchase_create(request):
    products = Product.objects.filter(is_active=True).order_by('name')
    products_json = []
    for p in products:
        products_json.append({
            'id': p.id,
            'name': p.name,
            'brand': p.brand,
            'code': p.product_code,
            'unit': p.get_unit_display(),
            'purchase_cost': str(p.purchase_cost_per_unit),
            'current_stock': str(p.current_stock),
        })

    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        costs = request.POST.getlist('cost[]')

        items_data = []
        for i in range(len(product_ids)):
            if product_ids[i]:
                items_data.append({
                    'product_id': product_ids[i],
                    'quantity_purchased': quantities[i] if i < len(quantities) else '1',
                    'purchase_cost_per_unit': costs[i] if i < len(costs) else '0',
                })

        purchase_data = {
            'invoice_number': request.POST.get('invoice_number', '').strip(),
            'purchase_date': request.POST.get('purchase_date') or timezone.localdate(),
            'supplier_name': request.POST.get('supplier_name', '').strip(),
            'payment_status': request.POST.get('payment_status', 'paid'),
            'amount_paid': request.POST.get('amount_paid', '0'),
            'payment_method': request.POST.get('payment_method', 'cash'),
            'notes': request.POST.get('notes', '').strip(),
        }

        try:
            purchase = create_purchase_order(purchase_data, items_data)
            messages.success(request, f"Purchase from '{purchase.supplier_name}' for ₹{purchase.total_amount} was successfully recorded and stock updated.")
            return redirect('purchases:purchase_detail', pk=purchase.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Error saving purchase: {str(e)}")

    else:
        form = PurchaseForm(initial={'purchase_date': timezone.localdate()})

    return render(request, 'purchases/purchase_form.html', {
        'form': form,
        'products': products,
        'products_json': json.dumps(products_json),
    })


def purchase_detail(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    items = purchase.items.select_related('product').all()

    return render(request, 'purchases/purchase_detail.html', {
        'purchase': purchase,
        'items': items,
    })


def purchase_void(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            void_purchase_order(purchase, reason=reason)
            messages.warning(request, f"Purchase invoice #{purchase.id} has been voided. Stock was adjusted.")
            return redirect('purchases:purchase_detail', pk=purchase.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Error voiding purchase: {str(e)}")

    return render(request, 'purchases/purchase_void_confirm.html', {'purchase': purchase})


def purchase_csv_upload(request):
    from .csv_services import import_purchases_from_csv
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'purchases/upload_csv.html')

        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a file ending with .csv")
            return render(request, 'purchases/upload_csv.html')

        try:
            invoices, items, errors = import_purchases_from_csv(csv_file)
            if errors:
                for err in errors[:5]:
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"...and {len(errors) - 5} more error(s).")
            if invoices > 0:
                messages.success(request, f"Purchases CSV Import complete: {invoices} invoice(s) created with {items} product items.")
                return redirect('purchases:purchase_list')
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")

    return render(request, 'purchases/upload_csv.html')


def purchase_csv_sample(request):
    from .csv_services import get_purchases_sample_csv
    return get_purchases_sample_csv()

