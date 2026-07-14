from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.utils import timezone
from .models import UserProfile, Dog

User = get_user_model()


class CalmDogSignupForm(forms.Form):
    """Doplňkový formulář k allauth registraci – jméno a příjmení.

    Nastaveno přes ACCOUNT_SIGNUP_FORM_CLASS. Allauth doplní pole
    e-mail + heslo + potvrzení hesla; metoda `signup` je zavolána po
    vytvoření uživatele.
    """

    first_name = forms.CharField(label="Jméno", max_length=150)
    last_name = forms.CharField(label="Příjmení", max_length=150)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "given-name"}
        )
        self.fields["last_name"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "family-name"}
        )

    def signup(self, request, user):
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save(update_fields=["first_name", "last_name"])


class BrandedSetPasswordForm(SetPasswordForm):
    """SetPasswordForm s .form-control, aby pole dědila jednotný vzhled webu."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
            field.widget.attrs.setdefault("autocomplete", "new-password")
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

        # Správné klávesnice na mobilu + automatické doplňování prohlížeče
        autocomplete_tokens = {
            "first_name": "given-name",
            "last_name": "family-name",
            "phone": "tel",
            "street": "address-line1",
            "city": "address-level2",
            "zip_code": "postal-code",
            "country": "country-name",
            "invoice_name": "billing organization",
            "invoice_street": "billing address-line1",
            "invoice_city": "billing address-level2",
            "invoice_zip": "billing postal-code",
            "invoice_country": "billing country-name",
        }
        inputmode_tokens = {
            "phone": "tel",
            "zip_code": "numeric",
            "invoice_zip": "numeric",
        }
        for name, token in autocomplete_tokens.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("autocomplete", token)
        for name, mode in inputmode_tokens.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("inputmode", mode)

    def save(self, commit=True):
        profile = super().save(commit=False)

        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]

        if commit:
            self.user.save()
            profile.save()

        return profile


class UserNotificationsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["marketing_consent", "review_request_opt_in"]
        labels = {
            "marketing_consent": "Chci dostávat novinky a nabídky e-mailem (newsletter)",
            "review_request_opt_in": "Chci dostat e-mail se žádostí o recenzi po nákupu",
        }
        widgets = {
            "marketing_consent": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "review_request_opt_in": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        profile = super().save(commit=False)
        if "marketing_consent" in self.changed_data:
            profile.marketing_consent_updated_at = timezone.now()
        if commit:
            profile.save()
        return profile


class DogForm(forms.ModelForm):
    class Meta:
        model = Dog
        fields = [
            "name", "breed", "sex", "birth_date",
            "is_neutered", "weight", "color", "chip_number",
            "vaccinated_on", "dewormed_on", "diet", "photo", "notes",
        ]
        labels = {
            "name": "Jméno psa",
            "breed": "Plemeno",
            "sex": "Pohlaví",
            "birth_date": "Datum narození",
            "is_neutered": "Kastrace",
            "weight": "Hmotnost (kg)",
            "color": "Barva srsti",
            "chip_number": "Číslo čipu / tetování",
            "vaccinated_on": "Poslední očkování",
            "dewormed_on": "Poslední odčervení",
            "diet": "Dieta / krmení",
            "photo": "Fotografie",
            "notes": "Poznámky",
        }
        widgets = {
            "breed": forms.TextInput(attrs={
                "list": "dog-breeds",
                "autocomplete": "off",
                "placeholder": "Začněte psát nebo vyberte…",
            }),
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "vaccinated_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "dewormed_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "weight": forms.NumberInput(attrs={"step": "0.1", "min": "0", "inputmode": "decimal"}),
            "diet": forms.TextInput(attrs={"placeholder": "např. bezobilné, 2× denně"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)
