# Generated by Django 4.2.6 on 2023-11-23 15:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("issue", "0001_initial"),
        ("article", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="issue",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="issue.issue",
            ),
        ),
    ]
