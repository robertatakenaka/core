# Generated by Django 4.1.10 on 2023-08-24 13:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("journal", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="officialjournal",
            name="final_number",
            field=models.CharField(
                blank=True, max_length=2, null=True, verbose_name="Final Number"
            ),
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="final_volume",
            field=models.CharField(
                blank=True, max_length=2, null=True, verbose_name="Final Volume"
            ),
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="initial_number",
            field=models.CharField(
                blank=True, max_length=1, null=True, verbose_name="Initial Number"
            ),
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="initial_volume",
            field=models.CharField(
                blank=True, max_length=1, null=True, verbose_name="Initial Volume"
            ),
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="iso_short_title",
            field=models.TextField(
                blank=True, null=True, verbose_name="ISO Short Title"
            ),
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="terminate_month",
            field=models.CharField(
                blank=True, max_length=8, null=True, verbose_name="Terminate month"
            ),
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="terminate_year",
            field=models.CharField(
                blank=True, max_length=8, null=True, verbose_name="Terminate year"
            ),
        ),
        migrations.CreateModel(
            name="JournalParallelTitles",
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
                ("text", models.TextField(blank=True, null=True, verbose_name="Texto")),
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
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="officialjournal",
            name="parallel_titles",
            field=models.ManyToManyField(
                blank=True, null=True, to="journal.journalparalleltitles"
            ),
        ),
    ]
