# Generated by Django 5.1.6 on 2025-02-25 09:52

import django_countries.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('isa_api', '0014_study_experiment_factor_description_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='institution',
            name='address_country',
            field=django_countries.fields.CountryField(max_length=2),
        ),
    ]
