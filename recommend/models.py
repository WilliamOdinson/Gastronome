from django.conf import settings
from django.db import models
from business.models import Business


class Click(models.Model):
    """
    One page-view event on a Business detail page.
    Logged-in users have a foreign key; 
    anonymous visitors are tracked via their Django session key.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="clicks")
    session_key = models.CharField(max_length=40, null=True, blank=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="clicks")
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "ts"]),
            models.Index(fields=["user", "ts"]),
            models.Index(fields=["session_key", "ts"]),
        ]
        ordering = ["-ts"]

    def __str__(self) -> str:
        who = self.user_id or self.session_key or "anon"
        return f"{who} -> {self.business_id} @ {self.ts:%Y-%m-%d %H:%M:%S}"
