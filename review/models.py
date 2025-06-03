from django.db import models
from business.models import Business
from django.utils import timezone
from user.models import User


class Review(models.Model):
    """
    User-generated review for a specific business.
    """
    review_id = models.CharField(max_length=22, primary_key=True, unique=True, verbose_name="Review ID")
    user = models.ForeignKey(User, related_name="reviews", on_delete=models.CASCADE, verbose_name="Author")
    business = models.ForeignKey(Business, related_name="reviews", on_delete=models.CASCADE, verbose_name="Business")
    stars = models.PositiveSmallIntegerField(verbose_name="Rating")
    date = models.DateTimeField(default=timezone.now, verbose_name="Date")
    text = models.TextField(verbose_name="Text")
    useful = models.PositiveIntegerField(default=0, verbose_name="Useful")
    funny = models.PositiveIntegerField(default=0, verbose_name="Funny")
    cool = models.PositiveIntegerField(default=0, verbose_name="Cool")
    
    # Auto rating based on user review text
    auto_score = models.FloatField(null=True, blank=True, verbose_name="Auto-Score")
    
    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['business']),
            models.Index(fields=['stars']),
        ]

    def __str__(self):
        if self.auto_score==self.stars or self.auto_score is None:
            return f"Review by {self.user.display_name} for {self.business.name} ({self.stars} stars, fair)"
        else:
            return f"Review by {self.user.display_name} for {self.business.name} ({self.stars} stars, not-fair)"


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
        verbose_name = "Tip"
        verbose_name_plural = "Tips"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['business']),
        ]

    def __str__(self):
        return f"Tip by {self.user.display_name} for {self.business.name}"
