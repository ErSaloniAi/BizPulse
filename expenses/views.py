from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
# Authentication requirement removed for personal use mode
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from .models import Expense, ExpenseCategory
from .forms import ExpenseForm, ExpenseCategoryForm


def expense_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    payment_filter = request.GET.get('payment_status', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    expenses = Expense.objects.select_related('category').all().order_by('-date', '-created_at')

    if category_id:
        expenses = expenses.filter(category_id=category_id)

    if payment_filter:
        expenses = expenses.filter(payment_status=payment_filter)

    if start_date:
        expenses = expenses.filter(date__gte=start_date)

    if end_date:
        expenses = expenses.filter(date__lte=end_date)

    if query:
        expenses = expenses.filter(
            Q(description__icontains=query) |
            Q(paid_to__icontains=query) |
            Q(receipt_reference__icontains=query) |
            Q(category__name__icontains=query)
        )

    total_incurred = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_paid = expenses.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_outstanding = expenses.aggregate(total=Sum('outstanding_amount'))['total'] or Decimal('0.00')

    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = ExpenseCategory.objects.all().order_by('name')

    return render(request, 'expenses/expense_list.html', {
        'page_obj': page_obj,
        'query': query,
        'category_id': category_id,
        'payment_filter': payment_filter,
        'start_date': start_date,
        'end_date': end_date,
        'categories': categories,
        'total_incurred': total_incurred,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
    })


def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save()
            messages.success(request, f"Expense '{expense.description}' for ₹{expense.amount} was recorded.")
            return redirect('expenses:expense_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ExpenseForm()

    return render(request, 'expenses/expense_form.html', {
        'form': form,
        'action_title': 'Record Operating Expense',
        'is_edit': False,
    })


def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            expense = form.save()
            messages.success(request, f"Expense '{expense.description}' was updated.")
            return redirect('expenses:expense_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ExpenseForm(instance=expense)

    return render(request, 'expenses/expense_form.html', {
        'form': form,
        'expense': expense,
        'action_title': f'Edit Expense: {expense.description}',
        'is_edit': True,
    })


def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        desc = expense.description
        amount = expense.amount
        expense.delete()
        messages.warning(request, f"Expense '{desc}' (₹{amount}) was deleted.")
        return redirect('expenses:expense_list')

    return render(request, 'expenses/expense_confirm_delete.html', {'expense': expense})


def category_list(request):
    categories = ExpenseCategory.objects.all().order_by('name')
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' was created.")
            return redirect('expenses:category_list')
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = ExpenseCategoryForm()

    return render(request, 'expenses/category_list.html', {
        'categories': categories,
        'form': form,
    })


def expense_csv_upload(request):
    from .csv_services import import_expenses_from_csv
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'expenses/upload_csv.html')

        if not csv_file.name.lower().endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a file ending with .csv")
            return render(request, 'expenses/upload_csv.html')

        try:
            created, errors = import_expenses_from_csv(csv_file)
            if errors:
                for err in errors[:5]:
                    messages.error(request, err)
                if len(errors) > 5:
                    messages.error(request, f"...and {len(errors) - 5} more error(s).")
            if created > 0:
                messages.success(request, f"Expenses CSV Import complete: {created} expense record(s) created.")
                return redirect('expenses:expense_list')
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")

    return render(request, 'expenses/upload_csv.html')


def expense_csv_sample(request):
    from .csv_services import get_expenses_sample_csv
    return get_expenses_sample_csv()

