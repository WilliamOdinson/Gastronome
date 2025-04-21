from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Custom user model representing a Yelp user, extending Django's built-in AbstractUser.
    """
    user_id = models.CharField(max_length=22, primary_key=True, unique=True, verbose_name="Yelp User ID")
    username = models.CharField(max_length=150, unique=True, verbose_name="Username")
    email = models.EmailField(max_length=254, unique=True, null=True, blank=True, verbose_name="User's Email")
    yelping_since = models.DateField(null=True, blank=True, verbose_name="Years Since Registration")
    review_count = models.PositiveIntegerField(default=0, verbose_name="Review Count")
    useful = models.PositiveIntegerField(default=0, verbose_name="Useful Votes")
    funny = models.PositiveIntegerField(default=0, verbose_name="Funny Votes")
    cool = models.PositiveIntegerField(default=0, verbose_name="Cool Votes")
    fans = models.PositiveIntegerField(default=0, verbose_name="Number of Fans")
    average_stars = models.FloatField(default=0.0, verbose_name="Average Stars")

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

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    
    class Meta:
        indexes = [
            models.Index(fields=["review_count"]),
            models.Index(fields=["fans"]),
        ]


    def __str__(self):
        return self.username

class Friendship(models.Model):
    """
    Represents friendship connections between users.
    """
    user = models.ForeignKey(
        User, related_name="friends", on_delete=models.CASCADE
    )
    friend = models.ForeignKey(
        User, related_name="friend_of", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('user', 'friend')
        indexes = [
            models.Index(fields=["user", "friend"]),
            models.Index(fields=["friend"]),
        ]


    def __str__(self):
        return f"{self.user.username} is friends with {self.friend.username}"
