# Generated by Django 4.2.6 on 2023-12-04 10:24

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("institution", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Affiliation",
            fields=[
                (
                    "institution_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="institution.institution",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("institution.institution",),
        ),
        migrations.CreateModel(
            name="PersonName",
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
                    "declared_name",
                    models.TextField(
                        blank=True,
                        max_length=256,
                        null=True,
                        verbose_name="Declared Name",
                    ),
                ),
                (
                    "given_names",
                    models.CharField(
                        blank=True,
                        max_length=128,
                        null=True,
                        verbose_name="Given names",
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=64, null=True, verbose_name="Last name"
                    ),
                ),
                (
                    "suffix",
                    models.CharField(
                        blank=True, max_length=64, null=True, verbose_name="Suffix"
                    ),
                ),
                (
                    "prefix",
                    models.CharField(
                        blank=True, max_length=64, null=True, verbose_name="Prefix"
                    ),
                ),
                (
                    "fullname",
                    models.TextField(
                        blank=True, max_length=256, null=True, verbose_name="Full Name"
                    ),
                ),
                (
                    "gender_identification_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("DECLARED", "Declarado por el investigador"),
                            (
                                "AUTOMATIC",
                                "Identificado automáticamente por programa de computador",
                            ),
                            ("MANUAL", "Identificado por algun usuario"),
                        ],
                        max_length=16,
                        null=True,
                        verbose_name="Gender identification status",
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
                    "gender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.gender",
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
            name="Researcher",
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
                    "year",
                    models.CharField(
                        blank=True, max_length=4, null=True, verbose_name="Year"
                    ),
                ),
                (
                    "affiliation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="researcher.affiliation",
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
                    "person_name",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="researcher.personname",
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
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ResearcherIdentifier",
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
                    "identifier",
                    models.CharField(
                        blank=True, max_length=64, null=True, verbose_name="ID"
                    ),
                ),
                (
                    "source_name",
                    models.CharField(
                        blank=True, max_length=64, null=True, verbose_name="Source name"
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
            name="ResearcherAKA",
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
                    "sort_order",
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    "researcher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="researcher.researcher",
                    ),
                ),
                (
                    "researcher_identifier",
                    modelcluster.fields.ParentalKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="researcher_also_known_as",
                        to="researcher.researcheridentifier",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order"],
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="researcheridentifier",
            index=models.Index(
                fields=["identifier"], name="researcher__identif_36fd65_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="researcheridentifier",
            index=models.Index(
                fields=["source_name"], name="researcher__source__6ebe2a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="personname",
            index=models.Index(
                fields=["fullname"], name="researcher__fullnam_76d678_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="personname",
            index=models.Index(
                fields=["last_name"], name="researcher__last_na_4ba2b0_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="personname",
            index=models.Index(
                fields=["declared_name"], name="researcher__declare_95a8e7_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="personname",
            unique_together={
                ("declared_name", "gender"),
                ("fullname", "last_name", "given_names", "suffix", "gender"),
            },
        ),
    ]
