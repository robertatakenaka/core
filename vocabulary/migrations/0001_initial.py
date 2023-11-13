# Generated by Django 4.2.6 on 2023-11-13 13:53

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Vocabulary",
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
                    "name",
                    models.TextField(
                        blank=True, null=True, verbose_name="Vocabulary name"
                    ),
                ),
                (
                    "acronym",
                    models.CharField(
                        blank=True,
                        max_length=10,
                        null=True,
                        verbose_name="Vocabulary acronym",
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
        ),
        migrations.CreateModel(
            name="Keyword",
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
                ("text", models.TextField(blank=True, null=True, verbose_name="Texto")),
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
                (
                    "vocabulary",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="vocabulary.vocabulary",
                        verbose_name="Vocabulary",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="vocabulary",
            index=models.Index(fields=["name"], name="vocabulary__name_c567ee_idx"),
        ),
        migrations.AddIndex(
            model_name="vocabulary",
            index=models.Index(
                fields=["acronym"], name="vocabulary__acronym_5db9d3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="keyword",
            index=models.Index(fields=["text"], name="vocabulary__text_492e2a_idx"),
        ),
        migrations.AddIndex(
            model_name="keyword",
            index=models.Index(
                fields=["language"], name="vocabulary__languag_479020_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="keyword",
            index=models.Index(
                fields=["vocabulary"], name="vocabulary__vocabul_ff8b36_idx"
            ),
        ),
    ]
