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
    display_name = models.CharField(max_length=150, verbose_name="Nickname")
    # After the importing the email field, we need to set the email field as no longer blank nor null
    email = models.EmailField(max_length=254, unique=True, null=False, blank=False, verbose_name="Email")
    # email = models.EmailField(max_length=254, unique=True, null=True, blank=True, verbose_name="Email")
    yelping_since = models.DateField(null=True, blank=True, verbose_name="Years Since Registration")
    review_count = models.PositiveIntegerField(default=0, verbose_name="Review Cnt.")
    useful = models.PositiveIntegerField(default=0, verbose_name="Useful")
    funny = models.PositiveIntegerField(default=0, verbose_name="Funny")
    cool = models.PositiveIntegerField(default=0, verbose_name="Cool")
    fans = models.PositiveIntegerField(default=0, verbose_name="Fans")
    average_stars = models.FloatField(default=0.0, verbose_name="Avg. Stars")

    friends = models.JSONField(default=list, blank=True, verbose_name="Friends")
    elite_years = models.JSONField(default=list, blank=True, verbose_name="Elite Years")

    compliment_hot = models.PositiveIntegerField(default=0, verbose_name="Hot")
    compliment_more = models.PositiveIntegerField(default=0, verbose_name="More")
    compliment_profile = models.PositiveIntegerField(default=0, verbose_name="Profile")
    compliment_cute = models.PositiveIntegerField(default=0, verbose_name="Cute")
    compliment_list = models.PositiveIntegerField(default=0, verbose_name="List")
    compliment_note = models.PositiveIntegerField(default=0, verbose_name="Note")
    compliment_plain = models.PositiveIntegerField(default=0, verbose_name="Plain")
    compliment_cool = models.PositiveIntegerField(default=0, verbose_name="Cool")
    compliment_funny = models.PositiveIntegerField(default=0, verbose_name="Funny")
    compliment_writer = models.PositiveIntegerField(default=0, verbose_name="Writer")
    compliment_photos = models.PositiveIntegerField(default=0, verbose_name="Photo")

    # After the importing the email field, we need to set the email field as a required field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_id']
    # USERNAME_FIELD = 'user_id'
    # REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["review_count"]),
            models.Index(fields=["fans"]),
        ]

    def __str__(self):
        if self.display_name and self.email:
            return f"{self.display_name} ({self.email})"
        return str(self.pk)
