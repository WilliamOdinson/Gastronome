import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("business", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tip",
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
                ("text", models.TextField(verbose_name="Tip Text")),
                ("date", models.DateTimeField(verbose_name="Tip Date")),
                (
                    "compliment_count",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Compliment Count"
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
            },
        ),
        migrations.CreateModel(
            name="Review",
            fields=[
                (
                    "review_id",
                    models.CharField(
                        max_length=22,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                        verbose_name="Review ID",
                    ),
                ),
                ("stars", models.PositiveSmallIntegerField(verbose_name="Star Rating")),
                (
                    "date",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Review Date"
                    ),
                ),
                ("text", models.TextField(verbose_name="Review Text")),
                (
                    "useful",
                    models.PositiveIntegerField(default=0, verbose_name="Useful Votes"),
                ),
                (
                    "funny",
                    models.PositiveIntegerField(default=0, verbose_name="Funny Votes"),
                ),
                (
                    "cool",
                    models.PositiveIntegerField(default=0, verbose_name="Cool Votes"),
                ),
                (
                    "auto_score",
                    models.FloatField(
                        blank=True, null=True, verbose_name="Model automatic scoring"
                    ),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="business.business",
                        verbose_name="Business Reviewed",
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
            },
        ),
    ]
