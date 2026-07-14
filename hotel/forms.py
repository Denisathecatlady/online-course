from django import forms
from .models import HotelReservation
from courses.recaptcha import verify_recaptcha


class HotelReservationForm(forms.ModelForm):
    terms = forms.BooleanField(
        required=True,
        label="Souhlasím s obchodními podmínkami a zpracováním osobních údajů",
        error_messages={"required": "Souhlas s podmínkami je povinný."},
    )

    # Honeypot – lidé ho nevidí, boti ho běžně vyplní.
    website = forms.CharField(required=False)
    recaptcha_token = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = HotelReservation
        fields = [
            "first_name", "last_name", "email", "phone",
            "date_from", "date_to",
            "pet_type", "pet_count", "pet_name", "pet_breed",
            "is_aggressive", "aggression_notes",
            "notes",
        ]
        widgets = {
            "date_from": forms.DateInput(
                attrs={"type": "text", "autocomplete": "off", "placeholder": "Vyberte datum"},
                format="%Y-%m-%d",
            ),
            "date_to": forms.DateInput(
                attrs={"type": "text", "autocomplete": "off", "placeholder": "Vyberte datum"},
                format="%Y-%m-%d",
            ),
            "aggression_notes": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        # Správné klávesnice na mobilu + automatické doplňování prohlížeče
        autocomplete_tokens = {
            "first_name": "given-name",
            "last_name": "family-name",
            "email": "email",
            "phone": "tel",
        }
        inputmode_tokens = {
            "email": "email",
            "phone": "tel",
        }
        for name, token in autocomplete_tokens.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("autocomplete", token)
        for name, mode in inputmode_tokens.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("inputmode", mode)

    def clean(self):
        cleaned = super().clean()

        self.is_spam = bool(cleaned.get("website"))
        if not self.is_spam:
            if not verify_recaptcha(self.request, cleaned.get("recaptcha_token", ""), "hotel_reservation"):
                raise forms.ValidationError(
                    "Nepodařilo se ověřit, že nejste robot. Zkuste to prosím znovu."
                )

        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to:
            if date_to <= date_from:
                raise forms.ValidationError("Datum odjezdu musí být po datu příjezdu.")
        return cleaned
