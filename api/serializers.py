from rest_framework import serializers
from review.models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Only allow the client to submit the star rating and content; other fields are automatically completed by the server.
    """
    class Meta:
        model = Review
        fields = ["stars", "text"]

    def validate_stars(self, value: int) -> int:
        if 1 <= value <= 5:
            return value
        raise serializers.ValidationError("The star rating must be between 1 and 5.")
