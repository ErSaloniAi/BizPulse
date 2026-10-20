from django.db import migrations

DEFAULT_CATEGORIES = [
    'Rent',
    'Electricity',
    'Water',
    'Internet and Telephone',
    'Transportation and Delivery',
    'Marketing and Advertising',
    'Repairs and Maintenance',
    'Packaging',
    'Employee Salaries',
    'Bank Charges',
    'Cleaning',
    'Software and Subscriptions',
    'Licences and Fees',
    'Other Business Expenses',
]


def seed_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model('expenses', 'ExpenseCategory')
    for cat_name in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.get_or_create(
            name=cat_name,
            defaults={'is_default': True}
        )


def reverse_seed_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model('expenses', 'ExpenseCategory')
    ExpenseCategory.objects.filter(name__in=DEFAULT_CATEGORIES, is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_seed_categories),
    ]
