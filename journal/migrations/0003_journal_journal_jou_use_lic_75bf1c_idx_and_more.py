# Generated by Django 4.2.6 on 2023-11-09 19:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("journal", "0002_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="journal",
            index=models.Index(
                fields=["use_license"], name="journal_jou_use_lic_75bf1c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="journal",
            index=models.Index(
                fields=["publishing_model"], name="journal_jou_publish_6139c2_idx"
            ),
        ),
    ]
