# Generated by Django 5.1.6 on 2025-02-26 12:27

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('isa_api', '0018_alter_study_end_date_alter_study_start_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='institution',
            name='email',
        ),
        migrations.RemoveField(
            model_name='institution',
            name='phone',
        ),
    ]
