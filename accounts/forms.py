from django import forms
from django.contrib.auth import get_user_model
from .models import UserProfile

User = get_user_model()
class UserProfileForm(forms.ModelForm):

    first_name = forms.CharField(label="Jméno", required=False)
    last_name = forms.CharField(label="Příjmení", required=False)

    class Meta:
        model = UserProfile
        fields = [
            "phone",
            "street",
            "city",
            "zip_code",
            "country",
            "invoice_name",
            "invoice_street",
            "invoice_city",
            "invoice_zip",
            "invoice_country",
        ]
        labels = {
            "phone": "Telefon",
            "street": "Ulice a číslo popisné",
            "city": "Město",
            "zip_code": "PSČ",
            "country": "Stát",

            "invoice_name": "Fakturační jméno / Název firmy",
            "invoice_street": "Fakturační ulice",
            "invoice_city": "Fakturační město",
            "invoice_zip": "Fakturační PSČ",
            "invoice_country": "Fakturační stát",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.user = user

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        profile = super().save(commit=False)

        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]

        if commit:
            self.user.save()
            profile.save()

        return profile
