# Initialization: Set Email as the Login Field

This document describes how to configure the Django authentication system in the Gastronome project to use `email` as the primary login credential instead of the default `user_id`. **This is particularly important after importing the Yelp dataset, which includes user IDs but does not contain email addresses by default.** Once semantic scores and user data are fully populated and the `email` field is guaranteed to be complete and unique, the application can safely switch to email-based authentication.

## Prerequisites

Before initiating the setup to use email as the login field, confirm the following conditions are met:

* Ensure the `user_user` table does **not** contain any `NULL` values in the `email` field.
* Verify this requirement by executing the following SQL queries:

  ```sql
  SELECT COUNT(email) FROM user_user;
  SELECT COUNT(DISTINCT email) FROM user_user;
  ```

  Both query results should match exactly and equal the total number of users (e.g., `1987897`).

## 1  Modify the User Model

Edit your Django `User` model in `user/models.py` to set email as the unique login identifier. The final should be:

```python
class User(AbstractUser):
    """
    Custom user model representing a Yelp user, extending Django's built-in AbstractUser.
    """
    user_id = models.CharField(max_length=22, primary_key=True, unique=True, verbose_name="Yelp User ID")
    display_name = models.CharField(max_length=150, verbose_name="Display Name")
    # After the importing the email field, we need to set the email field as no longer blank nor null
    email = models.EmailField(max_length=254, unique=True, null=False, blank=False, verbose_name="User's Email")
    # email = models.EmailField(max_length=254, unique=True, null=True, blank=True, verbose_name="User's Email")
    yelping_since = models.DateField(null=True, blank=True, verbose_name="Years Since Registration")
    review_count = models.PositiveIntegerField(default=0, verbose_name="Review Count")
    useful = models.PositiveIntegerField(default=0, verbose_name="Useful Votes")
    funny = models.PositiveIntegerField(default=0, verbose_name="Funny Votes")
    cool = models.PositiveIntegerField(default=0, verbose_name="Cool Votes")
    fans = models.PositiveIntegerField(default=0, verbose_name="Number of Fans")
    average_stars = models.FloatField(default=0.0, verbose_name="Average Stars")

    friends = models.JSONField(default=list, blank=True, verbose_name="Friend List")
    elite_years = models.JSONField(default=list, blank=True, verbose_name="Elite Years")

    compliment_hot = models.PositiveIntegerField(default=0, verbose_name="Hot Compliments")
    compliment_more = models.PositiveIntegerField(default=0, verbose_name="More Compliments")
    compliment_profile = models.PositiveIntegerField(default=0, verbose_name="Profile Compliments")
    compliment_cute = models.PositiveIntegerField(default=0, verbose_name="Cute Compliments")
    compliment_list = models.PositiveIntegerField(default=0, verbose_name="List Compliments")
    compliment_note = models.PositiveIntegerField(default=0, verbose_name="Note Compliments")
    compliment_plain = models.PositiveIntegerField(default=0, verbose_name="Plain Compliments")
    compliment_cool = models.PositiveIntegerField(default=0, verbose_name="Cool Compliments")
    compliment_funny = models.PositiveIntegerField(default=0, verbose_name="Funny Compliments")
    compliment_writer = models.PositiveIntegerField(default=0, verbose_name="Writer Compliments")
    compliment_photos = models.PositiveIntegerField(default=0, verbose_name="Photo Compliments")

    # After the importing the email field, we need to set the email field as a required field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_id']
    # USERNAME_FIELD = 'user_id'
    # REQUIRED_FIELDS = []
    
    class Meta:
        indexes = [
            models.Index(fields=["review_count"]),
            models.Index(fields=["fans"]),
        ]


    def __str__(self):
        return self.username
```

## 2  Generate Database Migration

Create a new migration reflecting your changes:

```bash
python manage.py makemigrations
```

When prompted with the message:

```
It is impossible to change a nullable field 'email' on user to non-nullable without providing a default. This is because the database needs something to populate existing rows.
Please select a fix:
 1) Provide a one-off default now (will be set on all existing rows with a null value for this column)
 2) Ignore for now. Existing rows that contain NULL values will have to be handled manually, for example with a RunPython or RunSQL operation.
 3) Quit and manually define a default value in models.py.
Select an option:
```

Choose option **2**:

```
2) Ignore for now. Existing rows that contain NULL values will have to be handled manually, for example with a RunPython or RunSQL operation.
```

## 3  Apply the Migration

Apply the newly generated migration to update the database schema:

```bash
python manage.py migrate
```

After executing these steps, your system is configured to use the email field as the primary login credential.
