from django.db import models


class Category(models.Model):
    """
    Category tag for businesses, e.g., "Mexican", "Burgers".
    """
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Business(models.Model):
    """
    Business model representing a restaurant or service listing from the Yelp dataset.
    """
    business_id = models.CharField(max_length=22, unique=True, primary_key=True, verbose_name="Business ID")
    name = models.CharField(max_length=255, verbose_name="Business Name")
    address = models.CharField(max_length=255, verbose_name="Address")
    city = models.CharField(max_length=100, verbose_name="City")
    state = models.CharField(max_length=2, verbose_name="2 Character State Code")
    postal_code = models.CharField(max_length=20, verbose_name="Postal Code")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitude")
    stars = models.FloatField(verbose_name="Average Rating")
    review_count = models.IntegerField(verbose_name="Review Count")
    is_open = models.BooleanField(default=True, verbose_name="Is Open")

    categories = models.ManyToManyField(Category, related_name="businesses", verbose_name="Categories")
    attributes = models.JSONField(null=True, blank=True, verbose_name="Raw Attributes")
    

    class Meta:
        indexes = [
            models.Index(fields=['city', 'state']),
            models.Index(fields=['stars']),
            models.Index(fields=['review_count']),
            models.Index(fields=['is_open']),
        ]


    def __str__(self):
        return f"{self.name} ({self.city}, {self.state})"


class Hour(models.Model):
    """
    Weekly opening hours for a business.
    """
    DAYS_OF_WEEK = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    business = models.ForeignKey(Business, related_name="hours", on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK, verbose_name="Day of Week")
    open_time = models.TimeField(verbose_name="Opening Time")
    close_time = models.TimeField(verbose_name="Closing Time")

    class Meta:
        unique_together = ('business', 'day')

    def __str__(self):
        return f"{self.business.name} - {self.day}: {self.open_time}~{self.close_time}"


class Photo(models.Model):
    """
    Photo metadata for a business; images are hosted on AWS S3.
    """
    photo_id = models.CharField(max_length=22, unique=True, primary_key=True)
    business = models.ForeignKey(Business, related_name='photos', on_delete=models.CASCADE)
    caption = models.CharField(max_length=255, null=True, blank=True)
    label = models.CharField(max_length=50, null=True, blank=True)
    
    @property
    def image_url(self) -> str:
        base = settings.PHOTO_BASE_URL.rstrip('/')
        return f"{base}/{self.photo_id}.jpg"
    
    class Meta:
        indexes = [
            models.Index(fields=['label']),
        ]

    def __str__(self):
        return f"{self.business.name} - {self.label or 'Unlabeled'}"


class CheckIn(models.Model):
    """
    Check-in timestamps indicating popularity/activity for a specific business.
    """
    business = models.ForeignKey(Business, related_name="checkins", on_delete=models.CASCADE, verbose_name="Checked-in Business")
    checkin_time = models.DateTimeField(verbose_name="Check-in Timestamp")

    class Meta:
        indexes = [
            models.Index(fields=['business']),
            models.Index(fields=['checkin_time']),
        ]

    def __str__(self):
        return f"Check-in at {self.business.name} ({self.checkin_time})"
