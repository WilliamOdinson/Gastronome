import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("business", "0001_initial"),
        ("user", "0002_alter_user_email"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessState",
            fields=[],
            options={
                "verbose_name": "State hotlist cache",
                "verbose_name_plural": "State hotlist caches",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("business.business",),
        ),
        migrations.CreateModel(
            name="PersonalRec",
            fields=[],
            options={
                "verbose_name": "Personal rec cache",
                "verbose_name_plural": "Personal rec caches",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("user.user",),
        ),
        migrations.CreateModel(
            name="Click",
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
                ("session_key", models.CharField(blank=True, max_length=40, null=True)),
                ("ts", models.DateTimeField(auto_now_add=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clicks",
                        to="business.business",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="clicks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-ts"],
                "indexes": [
                    models.Index(
                        fields=["business", "ts"], name="recommend_c_busines_cd6cc0_idx"
                    ),
                    models.Index(
                        fields=["user", "ts"], name="recommend_c_user_id_11dfc0_idx"
                    ),
                    models.Index(
                        fields=["session_key", "ts"],
                        name="recommend_c_session_337ae0_idx",
                    ),
                ],
            },
        ),
    ]
