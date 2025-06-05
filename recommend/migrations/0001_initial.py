from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("business", "0001_initial"),
        ("user", "0002_alter_user_email"),
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
    ]
