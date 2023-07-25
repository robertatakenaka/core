# Generated by Django 4.1.8 on 2023-07-25 23:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pid_provider", "0007_remove_pidrequest_error_msg_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pidrequest",
            name="detail",
            field=models.JSONField(blank=True, null=True, verbose_name="Detail"),
        ),
        migrations.DeleteModel(
            name="PidProviderBadRequest",
        ),
    ]
