# Generated by Django 4.2.6 on 2023-11-07 19:33

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import xmlsps.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="XMLVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Creation date"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last update date"
                    ),
                ),
                (
                    "pid_v3",
                    models.CharField(
                        blank=True, max_length=23, null=True, verbose_name="PID v3"
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=xmlsps.models.xml_directory_path,
                    ),
                ),
                (
                    "finger_print",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_creator",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creator",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_last_mod_user",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updater",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["finger_print"], name="xmlsps_xmlv_finger__c27ac5_idx"
                    ),
                    models.Index(
                        fields=["pid_v3"], name="xmlsps_xmlv_pid_v3_1c9245_idx"
                    ),
                ],
            },
        ),
    ]
