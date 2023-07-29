# Generated by Django 4.1.8 on 2023-07-28 15:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("xmlsps", "0003_xmlsps_xml_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="xmlsps",
            name="is_published",
            field=models.BooleanField(
                blank=True, null=True, verbose_name="Is published"
            ),
        ),
    ]
