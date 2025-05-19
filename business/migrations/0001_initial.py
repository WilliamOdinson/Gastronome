import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
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
                ("name", models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="Business",
            fields=[
                (
                    "business_id",
                    models.CharField(
                        max_length=22,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                        verbose_name="Business ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=255, verbose_name="Business Name"),
                ),
                ("address", models.CharField(max_length=255, verbose_name="Address")),
                ("city", models.CharField(max_length=100, verbose_name="City")),
                (
                    "state",
                    models.CharField(
                        max_length=2, verbose_name="2 Character State Code"
                    ),
                ),
                (
                    "postal_code",
                    models.CharField(max_length=20, verbose_name="Postal Code"),
                ),
                (
                    "latitude",
                    models.DecimalField(
                        decimal_places=6, max_digits=9, verbose_name="Latitude"
                    ),
                ),
                (
                    "longitude",
                    models.DecimalField(
                        decimal_places=6, max_digits=9, verbose_name="Longitude"
                    ),
                ),
                ("stars", models.FloatField(verbose_name="Average Rating")),
                ("review_count", models.IntegerField(verbose_name="Review Count")),
                ("is_open", models.BooleanField(default=True, verbose_name="Is Open")),
                (
                    "attributes",
                    models.JSONField(
                        blank=True, null=True, verbose_name="Raw Attributes"
                    ),
                ),
                (
                    "categories",
                    models.ManyToManyField(
                        related_name="businesses",
                        to="business.category",
                        verbose_name="Categories",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CheckIn",
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
                    "checkin_time",
                    models.DateTimeField(verbose_name="Check-in Timestamp"),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checkins",
                        to="business.business",
                        verbose_name="Checked-in Business",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Hour",
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
                    "day",
                    models.CharField(
                        choices=[
                            ("Monday", "Monday"),
                            ("Tuesday", "Tuesday"),
                            ("Wednesday", "Wednesday"),
                            ("Thursday", "Thursday"),
                            ("Friday", "Friday"),
                            ("Saturday", "Saturday"),
                            ("Sunday", "Sunday"),
                        ],
                        max_length=10,
                        verbose_name="Day of Week",
                    ),
                ),
                ("open_time", models.TimeField(verbose_name="Opening Time")),
                ("close_time", models.TimeField(verbose_name="Closing Time")),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hours",
                        to="business.business",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Photo",
            fields=[
                (
                    "photo_id",
                    models.CharField(
                        max_length=22, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("caption", models.CharField(blank=True, max_length=255, null=True)),
                ("label", models.CharField(blank=True, max_length=50, null=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="business.business",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="business",
            index=models.Index(
                fields=["city", "state"], name="business_bu_city_ecf686_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="business",
            index=models.Index(fields=["stars"], name="business_bu_stars_d17cc8_idx"),
        ),
        migrations.AddIndex(
            model_name="business",
            index=models.Index(
                fields=["review_count"], name="business_bu_review__eae99a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="business",
            index=models.Index(
                fields=["is_open"], name="business_bu_is_open_57b4bf_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="checkin",
            index=models.Index(
                fields=["business"], name="business_ch_busines_ac1194_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="checkin",
            index=models.Index(
                fields=["checkin_time"], name="business_ch_checkin_0ba318_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="hour",
            unique_together={("business", "day")},
        ),
        migrations.AddIndex(
            model_name="photo",
            index=models.Index(fields=["label"], name="business_ph_label_85848e_idx"),
        ),
    ]
