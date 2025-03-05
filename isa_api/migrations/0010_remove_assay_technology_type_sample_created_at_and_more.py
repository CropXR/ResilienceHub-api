# Generated by Django 5.1.6 on 2025-02-24 15:52

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('isa_api', '0009_sample'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assay',
            name='technology_type',
        ),
        migrations.AddField(
            model_name='sample',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sample',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
