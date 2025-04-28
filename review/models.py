from django.db import models
from business.models import Business
from user.models import User


class Review(models.Model):
    """
    User-generated review for a specific business.
    """
    review_id = models.CharField(max_length=22, primary_key=True, unique=True, verbose_name="Review ID")
    user = models.ForeignKey(User, related_name="reviews", on_delete=models.CASCADE, verbose_name="Review Author")
    business = models.ForeignKey(Business, related_name="reviews", on_delete=models.CASCADE,verbose_name="Business Reviewed")
    stars = models.PositiveSmallIntegerField(verbose_name="Star Rating")
    date = models.DateTimeField(verbose_name="Review Date")
    text = models.TextField(verbose_name="Review Text")
    useful = models.PositiveIntegerField(default=0, verbose_name="Useful Votes")
    funny = models.PositiveIntegerField(default=0, verbose_name="Funny Votes")
    cool = models.PositiveIntegerField(default=0, verbose_name="Cool Votes")
    
    # Auto rating based on user review text
    auto_score = models.FloatField(null=True, blank=True, verbose_name="Model automatic scoring")
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['business']),
            models.Index(fields=['stars']),
        ]

    def __str__(self):
        return f"Review by {self.user.username} for {self.business.name} ({self.stars} stars)"


class Tip(models.Model):
    """
    Short tip or recommendation provided by a user about a business.
    """
    user = models.ForeignKey(User, related_name="tips", on_delete=models.CASCADE, verbose_name="Tip Author")
    business = models.ForeignKey(Business, related_name="tips", on_delete=models.CASCADE, verbose_name="Business Tipped")
    text = models.TextField(verbose_name="Tip Text")
    date = models.DateTimeField(verbose_name="Tip Date")
    compliment_count = models.PositiveIntegerField(default=0, verbose_name="Compliment Count")

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['business']),
        ]

    def __str__(self):
        return f"Tip by {self.user.username} for {self.business.name}"
