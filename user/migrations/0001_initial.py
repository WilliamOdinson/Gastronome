import django.contrib.auth.models
import django.contrib.auth.validators
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "user_id",
                    models.CharField(
                        max_length=22,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                        verbose_name="Yelp User ID",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(max_length=150, verbose_name="Display Name"),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                        null=True,
                        unique=True,
                        verbose_name="User's Email",
                    ),
                ),
                (
                    "yelping_since",
                    models.DateField(
                        blank=True, null=True, verbose_name="Years Since Registration"
                    ),
                ),
                (
                    "review_count",
                    models.PositiveIntegerField(default=0, verbose_name="Review Count"),
                ),
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
                    "fans",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Number of Fans"
                    ),
                ),
                (
                    "average_stars",
                    models.FloatField(default=0.0, verbose_name="Average Stars"),
                ),
                (
                    "friends",
                    models.JSONField(
                        blank=True, default=list, verbose_name="Friend List"
                    ),
                ),
                (
                    "elite_years",
                    models.JSONField(
                        blank=True, default=list, verbose_name="Elite Years"
                    ),
                ),
                (
                    "compliment_hot",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Hot Compliments"
                    ),
                ),
                (
                    "compliment_more",
                    models.PositiveIntegerField(
                        default=0, verbose_name="More Compliments"
                    ),
                ),
                (
                    "compliment_profile",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Profile Compliments"
                    ),
                ),
                (
                    "compliment_cute",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Cute Compliments"
                    ),
                ),
                (
                    "compliment_list",
                    models.PositiveIntegerField(
                        default=0, verbose_name="List Compliments"
                    ),
                ),
                (
                    "compliment_note",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Note Compliments"
                    ),
                ),
                (
                    "compliment_plain",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Plain Compliments"
                    ),
                ),
                (
                    "compliment_cool",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Cool Compliments"
                    ),
                ),
                (
                    "compliment_funny",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Funny Compliments"
                    ),
                ),
                (
                    "compliment_writer",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Writer Compliments"
                    ),
                ),
                (
                    "compliment_photos",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Photo Compliments"
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["review_count"], name="user_user_review__3b8c2d_idx"
                    ),
                    models.Index(fields=["fans"], name="user_user_fans_1ca852_idx"),
                ],
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
