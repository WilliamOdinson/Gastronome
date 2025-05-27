from django import forms
from review.models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["stars", "text"]
        widgets = {
            "stars": forms.NumberInput(
                attrs={
                    "min": 1,
                    "max": 5,
                    "class": "form-control w-auto d-inline-block ms-2",
                }
            ),
            "text": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control auto-expand",
                    "style": "overflow-y: hidden; max-height: 300px; transition: height 0.2s ease; resize: none;"
                }
            )
        }

    def clean_text(self):
        text = self.cleaned_data.get("text", "").strip()
        if not text:
            raise forms.ValidationError("This field is required.")
        return text
