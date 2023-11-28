# Generated by Django 4.2.6 on 2023-11-23 15:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("wagtaildocs", "0012_uploadeddocument"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CopyrightHolderHistoryItem",
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
                    "initial_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Initial Date"
                    ),
                ),
                (
                    "final_date",
                    models.DateField(blank=True, null=True, verbose_name="Final Date"),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="EditorialManagerHistoryItem",
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
                    "initial_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Initial Date"
                    ),
                ),
                (
                    "final_date",
                    models.DateField(blank=True, null=True, verbose_name="Final Date"),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Institution",
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
                ("name", models.TextField(blank=True, null=True, verbose_name="Nome")),
                (
                    "institution_type",
                    models.TextField(
                        blank=True,
                        choices=[
                            ("", ""),
                            (
                                "agência de apoio à pesquisa",
                                "agência de apoio à pesquisa",
                            ),
                            (
                                "universidade e instâncias ligadas à universidades",
                                "universidade e instâncias ligadas à universidades",
                            ),
                            (
                                "empresa ou instituto ligadas ao governo",
                                "empresa ou instituto ligadas ao governo",
                            ),
                            ("organização privada", "organização privada"),
                            (
                                "organização sem fins de lucros",
                                "organização sem fins de lucros",
                            ),
                            (
                                "sociedade científica, associação pós-graduação, associação profissional",
                                "sociedade científica, associação pós-graduação, associação profissional",
                            ),
                            ("outros", "outros"),
                        ],
                        null=True,
                        verbose_name="Institution Type",
                    ),
                ),
                (
                    "acronym",
                    models.TextField(
                        blank=True, null=True, verbose_name="Institution Acronym"
                    ),
                ),
                (
                    "level_1",
                    models.TextField(
                        blank=True, null=True, verbose_name="Organization Level 1"
                    ),
                ),
                (
                    "level_2",
                    models.TextField(
                        blank=True, null=True, verbose_name="Organization Level 2"
                    ),
                ),
                (
                    "level_3",
                    models.TextField(
                        blank=True, null=True, verbose_name="Organization Level 3"
                    ),
                ),
                ("url", models.URLField(blank=True, null=True, verbose_name="url")),
                (
                    "logo",
                    models.ImageField(
                        blank=True, null=True, upload_to="", verbose_name="Logo"
                    ),
                ),
                (
                    "is_official",
                    models.CharField(
                        blank=True,
                        choices=[("yes", "yes"), ("no", "no"), ("unknow", "unknow")],
                        max_length=6,
                        null=True,
                        verbose_name="Is official",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InstitutionHistory",
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
                    "initial_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Initial Date"
                    ),
                ),
                (
                    "final_date",
                    models.DateField(blank=True, null=True, verbose_name="Final Date"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OwnerHistoryItem",
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
                    "initial_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Initial Date"
                    ),
                ),
                (
                    "final_date",
                    models.DateField(blank=True, null=True, verbose_name="Final Date"),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="PublisherHistoryItem",
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
                    "initial_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Initial Date"
                    ),
                ),
                (
                    "final_date",
                    models.DateField(blank=True, null=True, verbose_name="Final Date"),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Scimago",
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
                    "institution",
                    models.TextField(blank=True, null=True, verbose_name="Institution"),
                ),
                ("url", models.URLField(blank=True, null=True, verbose_name="url")),
            ],
        ),
        migrations.CreateModel(
            name="CopyrightHolder",
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
            name="EditorialManager",
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
            name="Owner",
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
            name="Publisher",
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
            name="Sponsor",
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
            name="SponsorHistoryItem",
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
                    "initial_date",
                    models.DateField(
                        blank=True, null=True, verbose_name="Initial Date"
                    ),
                ),
                (
                    "final_date",
                    models.DateField(blank=True, null=True, verbose_name="Final Date"),
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
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ScimagoFile",
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
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="wagtaildocs.document",
                    ),
                ),
            ],
        ),
    ]
