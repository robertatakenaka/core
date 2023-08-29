# Generated by Django 4.1.10 on 2023-08-29 13:10

from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields


class Migration(migrations.Migration):
    dependencies = [
        ("journal", "0002_remove_journal_name_remove_journal_url_and_more"),
        ("journal_and_collection", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="event",
            name="journal_and_occurre_474567_idx",
        ),
        migrations.RemoveField(
            model_name="event",
            name="occurrence_type",
        ),
        migrations.RemoveField(
            model_name="journalandcollection",
            name="journal",
        ),
        migrations.AddField(
            model_name="event",
            name="description_type",
            field=models.CharField(
                blank=True,
                choices=[("indexing", "Indexing"), ("deindexing", "Deindexing")],
                max_length=20,
                null=True,
                verbose_name="Description type",
            ),
        ),
        migrations.AddField(
            model_name="journalandcollection",
            name="scielo",
            field=modelcluster.fields.ParentalKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="journal_history",
                to="journal.scielojournal",
                verbose_name="Journal",
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="occurrence_date",
            field=models.CharField(
                blank=True, max_length=20, null=True, verbose_name="Occurrence date"
            ),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["description_type"], name="journal_and_descrip_78c132_idx"
            ),
        ),
    ]
