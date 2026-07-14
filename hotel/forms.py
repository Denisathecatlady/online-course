from django import forms
from .models import HotelReservation


class HotelReservationForm(forms.ModelForm):
    terms = forms.BooleanField(
        required=True,
        label="Souhlasím s obchodními podmínkami a zpracováním osobních údajů",
        error_messages={"required": "Souhlas s podmínkami je povinný."},
    )

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

    def __init__(self, *args, **kwargs):
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
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to:
            if date_to <= date_from:
                raise forms.ValidationError("Datum odjezdu musí být po datu příjezdu.")
        return cleaned
