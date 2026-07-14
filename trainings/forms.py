"""
Formuláře rezervačního systému.

Kontaktní údaje se předvyplní z profilu (viz `views.book_slot`), klient je
může upravit. Pole `dog_name` je povinné (jméno psa na profilu není).
Ověření dostupnosti slotu (obsazenost, minulost, blokace) probíhá atomicky
ve view pod zámkem – form řeší jen validaci polí.
"""

from django import forms

from .models import TrainingReservation


class TrainingBookingForm(forms.ModelForm):
    class Meta:
        model = TrainingReservation
        fields = ["first_name", "last_name", "email", "phone", "dog_name", "note"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "given-name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "family-name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "email"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "tel"}
            ),
            "dog_name": forms.TextInput(attrs={"class": "form-control"}),
            "note": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Cokoli, co by měl trenér vědět (nepovinné).",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email", "dog_name"):
            self.fields[name].required = True
