from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from config.csv_utils import (
    get_normalized_dict_reader,
    parse_decimal_safe,
    parse_date_safe,
    generate_csv_download,
)
from .models import Expense, ExpenseCategory


def get_field_val(row, candidates, default=''):
    for cand in candidates:
        if cand in row and row[cand]:
            return row[cand]
    return default


def resolve_or_create_category(category_name):
    clean = category_name.strip()
    if not clean:
        clean = "General / Miscellaneous"
    cat = ExpenseCategory.objects.filter(name__iexact=clean).first()
    if not cat:
        cat = ExpenseCategory.objects.create(name=clean, is_default=False)
    return cat


def import_expenses_from_csv(uploaded_file):
    """
    Parses and imports operating expense records from CSV.
    Auto-creates categories if they do not exist yet.
    Returns (created_count, errors_list).
    """
    rows = get_normalized_dict_reader(uploaded_file)
    if not rows:
        return 0, ["The uploaded CSV file is empty or missing valid headers."]

    created_count = 0
    errors = []

    with transaction.atomic():
        for row in rows:
            row_num = row.get('_row_num', '?')
            description = get_field_val(row, ['description', 'desc', 'expense_description', 'title', 'details'])
            if not description:
                errors.append(f"Row {row_num}: Description is required.")
                continue

            try:
                amount = parse_decimal_safe(
                    get_field_val(row, ['amount', 'expense_amount', 'total_amount', 'total']),
                    Decimal('0.00')
                )
                if amount <= Decimal('0.00'):
                    errors.append(f"Row {row_num}: Expense amount must be greater than zero.")
                    continue
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            try:
                date = parse_date_safe(
                    get_field_val(row, ['date', 'expense_date']),
                    timezone.localdate()
                )
            except ValueError as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue

            category_name = get_field_val(row, ['category', 'expense_category', 'type'], 'General / Miscellaneous')
            category = resolve_or_create_category(category_name)

            payment_status = get_field_val(row, ['payment_status', 'status', 'payment'], 'paid').lower()
            if payment_status not in ('paid', 'partial', 'unpaid'):
                payment_status = 'paid'

            payment_method = get_field_val(row, ['payment_method', 'method', 'mode'], 'cash').lower()
            if payment_method not in ('cash', 'upi', 'card', 'bank', 'other'):
                payment_method = 'cash'

            amount_paid_raw = get_field_val(row, ['amount_paid', 'paid'])
            if amount_paid_raw:
                try:
                    amount_paid = parse_decimal_safe(amount_paid_raw, Decimal('0.00'))
                except ValueError:
                    amount_paid = amount if payment_status == 'paid' else Decimal('0.00')
            else:
                if payment_status == 'paid':
                    amount_paid = amount
                elif payment_status == 'unpaid':
                    amount_paid = Decimal('0.00')
                else:
                    amount_paid = amount / Decimal('2.00')

            amount_paid = min(amount_paid, amount)
            paid_to = get_field_val(row, ['paid_to', 'vendor', 'payee', 'beneficiary'])
            receipt_ref = get_field_val(row, ['receipt_reference', 'receipt_no', 'reference', 'ref'])
            notes = get_field_val(row, ['notes', 'remarks', 'comment'])

            Expense.objects.create(
                category=category,
                date=date,
                description=description,
                amount=amount,
                payment_status=payment_status,
                amount_paid=amount_paid,
                payment_method=payment_method,
                paid_to=paid_to,
                receipt_reference=receipt_ref,
                notes=notes,
            )
            created_count += 1

    return created_count, errors


def get_expenses_sample_csv():
    headers = [
        "Date", "Category", "Description", "Amount", "Payment Status",
        "Amount Paid", "Payment Method", "Paid To", "Receipt Reference", "Notes"
    ]
    sample_rows = [
        ["2026-10-01", "Rent", "Monthly Shop Rent for October", "12000.00", "paid", "12000.00", "bank", "Landlord Gupta Ji", "RENT-OCT-2026", "Paid via NEFT"],
        ["2026-10-02", "Electricity", "Electricity bill for September", "1850.00", "paid", "1850.00", "upi", "State Electricity Board", "BILL-98214", "Online UPI payment"],
        ["2026-10-03", "Tea & Refreshments", "Daily tea and snacks for staff", "350.00", "paid", "350.00", "cash", "Sharma Tea Stall", "", "Weekly settlement"],
        ["2026-10-05", "Packaging", "Carry bags and packing tape rolls", "800.00", "paid", "800.00", "cash", "Metro Packaging", "", "Plastic and paper bags"],
        ["2026-10-07", "Repairs & Maintenance", "Display shelf lighting repair", "650.00", "paid", "650.00", "cash", "Local Electrician", "", "LED strip replacement"],
    ]
    return generate_csv_download("bizpulse_expenses_sample.csv", headers, sample_rows)
