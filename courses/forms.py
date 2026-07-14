from django import forms

from .recaptcha import verify_recaptcha


class ContactForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    subject = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea)

    # Honeypot – lidé ho nevidí, boti ho běžně vyplní.
    website = forms.CharField(required=False)
    recaptcha_token = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()

        self.is_spam = bool(cleaned.get("website"))
        if self.is_spam:
            return cleaned  # bot – nemá smysl dál ověřovat recaptcha

        if not verify_recaptcha(self.request, cleaned.get("recaptcha_token", ""), "contact"):
            raise forms.ValidationError(
                "Nepodařilo se ověřit, že nejste robot. Zkuste to prosím znovu."
            )
        return cleaned
