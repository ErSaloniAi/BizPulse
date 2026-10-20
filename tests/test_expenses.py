from decimal import Decimal
import datetime
from django.test import TestCase
from expenses.models import Expense, ExpenseCategory


class ExpenseTests(TestCase):
    def setUp(self):
        self.entry_date = datetime.date(2026, 1, 1)
        self.rent_cat, _ = ExpenseCategory.objects.get_or_create(name='Rent')
        self.elec_cat, _ = ExpenseCategory.objects.get_or_create(name='Electricity')

    def test_create_expense_paid(self):
        exp = Expense.objects.create(
            category=self.rent_cat,
            date=self.entry_date,
            description='Shop Rent January',
            amount=Decimal('10000.00'),
            amount_paid=Decimal('10000.00'),
            payment_status='paid',
        )
        self.assertEqual(exp.outstanding_amount, Decimal('0.00'))
        self.assertEqual(exp.payment_status, 'paid')

    def test_create_expense_partial(self):
        exp = Expense.objects.create(
            category=self.elec_cat,
            date=self.entry_date,
            description='Electricity Bill',
            amount=Decimal('2500.00'),
            amount_paid=Decimal('1000.00'),
        )
        self.assertEqual(exp.outstanding_amount, Decimal('1500.00'))
        self.assertEqual(exp.payment_status, 'partial')

    def test_create_expense_unpaid(self):
        exp = Expense.objects.create(
            category=self.rent_cat,
            date=self.entry_date,
            description='Pending Maintenance',
            amount=Decimal('800.00'),
            amount_paid=Decimal('0.00'),
        )
        self.assertEqual(exp.outstanding_amount, Decimal('800.00'))
        self.assertEqual(exp.payment_status, 'unpaid')
