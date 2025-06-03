from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    Custom manager for the User model, providing methods to create users and superusers.
    """
    def create_user(self, email, user_id, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        if not user_id:
            raise ValueError(_('The Yelp User ID field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, user_id=user_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, user_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, user_id, password, **extra_fields)


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
    
    objects = CustomUserManager()
    
    class Meta:
        indexes = [
            models.Index(fields=["review_count"]),
            models.Index(fields=["fans"]),
        ]


    def __str__(self):
        if self.display_name and self.email:
            return f"{self.display_name} ({self.email})"
        return str(self.pk)
