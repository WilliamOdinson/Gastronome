import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("business", "0001_initial"),
        ("review", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reviews",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Review Author",
            ),
        ),
        migrations.AddField(
            model_name="tip",
            name="business",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tips",
                to="business.business",
                verbose_name="Business Tipped",
            ),
        ),
        migrations.AddField(
            model_name="tip",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tips",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Tip Author",
            ),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(fields=["user"], name="review_revi_user_id_1c40d7_idx"),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(
                fields=["business"], name="review_revi_busines_96d39e_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="review",
            index=models.Index(fields=["stars"], name="review_revi_stars_bd5ed6_idx"),
        ),
        migrations.AddIndex(
            model_name="tip",
            index=models.Index(fields=["user"], name="review_tip_user_id_27ca54_idx"),
        ),
        migrations.AddIndex(
            model_name="tip",
            index=models.Index(
                fields=["business"], name="review_tip_busines_546b02_idx"
            ),
        ),
    ]
