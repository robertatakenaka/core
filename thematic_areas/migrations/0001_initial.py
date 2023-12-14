# Generated by Django 4.2.7 on 2023-12-14 10:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("wagtaildocs", "0012_uploadeddocument"),
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ThematicAreaFile",
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
                    "is_valid",
                    models.BooleanField(
                        blank=True, default=False, null=True, verbose_name="Is valid?"
                    ),
                ),
                (
                    "line_count",
                    models.IntegerField(
                        blank=True, default=0, null=True, verbose_name="Number of lines"
                    ),
                ),
                (
                    "attachment",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="wagtaildocs.document",
                        verbose_name="Attachment",
                    ),
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
                "verbose_name_plural": "Thematic Areas Upload",
            },
        ),
        migrations.CreateModel(
            name="GenericThematicAreaFile",
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
                    "is_valid",
                    models.BooleanField(
                        blank=True, default=False, null=True, verbose_name="Is valid?"
                    ),
                ),
                (
                    "line_count",
                    models.IntegerField(
                        blank=True, default=0, null=True, verbose_name="Number of lines"
                    ),
                ),
                (
                    "attachment",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="wagtaildocs.document",
                        verbose_name="Attachment",
                    ),
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
                "verbose_name_plural": "Generic Thematic Areas Upload",
            },
        ),
        migrations.CreateModel(
            name="ThematicArea",
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
                    "level0",
                    models.TextField(
                        blank=True,
                        help_text="Here the thematic colleges of CAPES must be registered, more about these areas access: https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/sobre-as-areas-de-avaliacao",
                        null=True,
                        verbose_name="Level 0",
                    ),
                ),
                (
                    "level1",
                    models.TextField(
                        blank=True,
                        help_text="Here the thematic colleges of CAPES must be registered, more about these areas access: https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/sobre-as-areas-de-avaliacao",
                        null=True,
                        verbose_name="Level 1",
                    ),
                ),
                (
                    "level2",
                    models.TextField(
                        blank=True,
                        help_text="Here the thematic colleges of CAPES must be registered, more about these areas access: https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/sobre-as-areas-de-avaliacao",
                        null=True,
                        verbose_name="Level 2",
                    ),
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
                "verbose_name": "Thematic Area",
                "verbose_name_plural": "Thematic Areas",
                "indexes": [
                    models.Index(
                        fields=["level0"], name="thematic_ar_level0_c26277_idx"
                    ),
                    models.Index(
                        fields=["level1"], name="thematic_ar_level1_ba9b9c_idx"
                    ),
                    models.Index(
                        fields=["level2"], name="thematic_ar_level2_a20cfc_idx"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="GenericThematicArea",
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
                    "text",
                    models.TextField(
                        blank=True, null=True, verbose_name="Thematic Area"
                    ),
                ),
                (
                    "origin",
                    models.TextField(
                        blank=True, null=True, verbose_name="Origin Data Base"
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", ""),
                            ("UNDEFINED", "UNDEFINED"),
                            ("0", "Level 0"),
                            ("1", "Level 1"),
                            ("2", "Level 2"),
                            ("3", "Level 3"),
                        ],
                        max_length=20,
                        null=True,
                        verbose_name="Nível",
                    ),
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
                    "language",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.language",
                        verbose_name="Idioma",
                    ),
                ),
                (
                    "level_up",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generic_thematic_area_level_up",
                        to="thematic_areas.genericthematicarea",
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
                "verbose_name": "Generic Thematic Area",
                "verbose_name_plural": "Generic Thematic Areas",
                "indexes": [
                    models.Index(fields=["text"], name="thematic_ar_text_6dca47_idx"),
                    models.Index(
                        fields=["origin"], name="thematic_ar_origin_b71fb9_idx"
                    ),
                    models.Index(fields=["level"], name="thematic_ar_level_5cd38d_idx"),
                ],
            },
        ),
    ]
