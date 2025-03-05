# Generated by Django 5.1.6 on 2025-02-26 09:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('isa_api', '0015_alter_institution_address_country'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investigationpermission',
            name='role',
            field=models.CharField(choices=[('viewer', 'Viewer'), ('contributor', 'Contributor'), ('owner', 'Owner')], default='viewer', max_length=20),
        ),
        migrations.AlterField(
            model_name='studypermission',
            name='role',
            field=models.CharField(choices=[('viewer', 'Viewer'), ('contributor', 'Contributor'), ('owner', 'Owner')], default='viewer', max_length=20),
        ),
    ]
