from django.db import migrations


def seed_business_setting(apps, schema_editor):
    BusinessSetting = apps.get_model('accounts', 'BusinessSetting')
    if not BusinessSetting.objects.exists():
        BusinessSetting.objects.create(
            shop_name='Shree Ganesh Stationery & Book Store',
            owner_name='Shopkeeper',
            phone='9876543210',
            email='store@bizpulse.local',
            address='Station Road, Market Complex, Shop No. 12',
            gstin='',
            currency_symbol='₹',
            default_low_stock_threshold=5
        )


def reverse_seed_business_setting(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_business_setting, reverse_seed_business_setting),
    ]
