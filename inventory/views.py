from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
# Authentication requirement removed for personal use mode
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from .models import Product, StockMovement
from .forms import ProductForm, StockAdjustmentForm
from .services import create_product_with_opening_stock, record_stock_adjustment


def product_list(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', 'all').strip()

    products = Product.objects.filter(is_active=True).prefetch_related('stock_movements').order_by('name')

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(product_code__icontains=query) |
            Q(category__icontains=query)
        )

    if category:
        products = products.filter(category__iexact=category)

    # Annotate/filter by stock condition in memory for precise calculation
    filtered_list = []
    for p in products:
        current = p.current_stock
        is_low = current <= p.minimum_stock_level
        is_out = current <= Decimal('0.00')

        if status_filter == 'low' and not is_low:
            continue
        elif status_filter == 'out' and not is_out:
            continue
        elif status_filter == 'in' and is_low:
            continue

        filtered_list.append({
            'product': p,
            'current_stock': current,
            'is_low_stock': is_low,
            'is_out_of_stock': is_out,
            'stock_value': current * p.weighted_avg_cost,
        })

    paginator = Paginator(filtered_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Distinct categories for filter dropdown
    categories = Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category')
    categories = [c for c in categories if c]

    return render(request, 'inventory/product_list.html', {
        'page_obj': page_obj,
        'query': query,
        'category': category,
        'status_filter': status_filter,
        'categories': categories,
        'total_count': len(filtered_list),
    })


def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = create_product_with_opening_stock(form.cleaned_data)
            messages.success(request, f"Product '{product.name}' was created successfully with opening stock of {product.opening_quantity} {product.get_unit_display()}.")
            return redirect('inventory:product_detail', pk=product.pk)
        else:
            if hasattr(form, 'duplicate_found'):
                messages.warning(request, "A similar product already exists. Please review the details or check the box to confirm duplicate entry.")
            else:
                messages.error(request, "Please correct the errors below.")
    else:
        form = ProductForm()

    categories = Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category')
    categories = [c for c in categories if c]

    return render(request, 'inventory/product_form.html', {
        'form': form,
        'action_title': 'Add Opening Stock / New Product',
        'is_edit': False,
        'categories': categories,
    })


def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product '{product.name}' details updated successfully.")
            return redirect('inventory:product_detail', pk=product.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProductForm(instance=product)

    categories = Product.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category')
    categories = [c for c in categories if c]

    return render(request, 'inventory/product_form.html', {
        'form': form,
        'product': product,
        'action_title': f'Edit Product: {product.name}',
        'is_edit': True,
        'categories': categories,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    movements = product.stock_movements.all()[:50]
    current_stock = product.current_stock

    return render(request, 'inventory/product_detail.html', {
        'product': product,
        'current_stock': current_stock,
        'is_low_stock': current_stock <= product.minimum_stock_level,
        'stock_value': current_stock * product.weighted_avg_cost,
        'movements': movements,
    })


def stock_adjustment(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            adj_type = form.cleaned_data['adjustment_type']
            qty = form.cleaned_data['quantity']
            date = form.cleaned_data['date']
            reason = form.cleaned_data['reason']
            notes = form.cleaned_data['notes']

            # Check if subtraction would lead to negative stock
            if adj_type == 'SUBTRACT' and qty > product.current_stock:
                form.add_error('quantity', f"Cannot deduct {qty} units. Current stock is only {product.current_stock} units.")
            else:
                record_stock_adjustment(product, adj_type, qty, date, reason, notes)
                action_word = "added" if adj_type == 'ADD' else "deducted"
                messages.success(request, f"Stock adjustment recorded: {qty} {product.get_unit_display()} {action_word} for '{product.name}'.")
                return redirect('inventory:product_detail', pk=product.pk)
    else:
        form = StockAdjustmentForm()

    return render(request, 'inventory/stock_adjustment.html', {
        'product': product,
        'form': form,
        'current_stock': product.current_stock,
    })


def low_stock_list(request):
    products = Product.objects.filter(is_active=True).prefetch_related('stock_movements').order_by('name')
    low_stock_items = []
    for p in products:
        current = p.current_stock
        if current <= p.minimum_stock_level:
            low_stock_items.append({
                'product': p,
                'current_stock': current,
                'deficit': max(p.minimum_stock_level - current, Decimal('0.00')),
            })

    return render(request, 'inventory/low_stock.html', {
        'low_stock_items': low_stock_items,
        'total_low_stock': len(low_stock_items),
    })


def product_api_lookup(request):
    """
    JSON API for dynamic product autocomplete and live stock/price lookup in sales/purchases forms.
    """
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(is_active=True)
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(product_code__icontains=query)
        )

    results = []
    for p in products[:30]:
        results.append({
            'id': p.id,
            'name': p.name,
            'brand': p.brand,
            'code': p.product_code,
            'unit': p.get_unit_display(),
            'selling_price': str(p.selling_price_per_unit),
            'purchase_cost': str(p.purchase_cost_per_unit),
            'current_stock': str(p.current_stock),
        })

    return JsonResponse({'results': results})


def product_csv_upload(request):
    from .csv_services import import_products_from_csv
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'inventory/upload_csv.html')

        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a file ending with .csv")
            return render(request, 'inventory/upload_csv.html')

        try:
            created, updated, errors = import_products_from_csv(csv_file)
            if errors:
                for err in errors[:5]:
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"...and {len(errors) - 5} more error(s).")
            if created > 0 or updated > 0:
                messages.success(request, f"Stock CSV Import complete: {created} product(s) created, {updated} updated.")
                return redirect('inventory:product_list')
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")

    return render(request, 'inventory/upload_csv.html')


def product_csv_sample(request):
    from .csv_services import get_product_sample_csv
    return get_product_sample_csv()

