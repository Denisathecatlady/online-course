from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Sociální přihlášení (Google).

    Pokud účet se stejným e-mailem už existuje a poskytovatel e-mail ověřil,
    propojíme sociální konto se stávajícím účtem místo vytvoření duplicitního.
    Připojujeme jen ověřené e-maily (Google `email_verified`), aby nešlo
    převzít cizí účet nepotvrzenou adresou.
    """

    def pre_social_login(self, request, sociallogin):
        # Sociální konto je už propojené s uživatelem – není co řešit.
        if sociallogin.is_existing:
            return

        email = (sociallogin.user.email or "").strip().lower()
        if not email:
            return

        # Propojíme jen když poskytovatel danou adresu ověřil.
        provider_verified = any(
            addr.verified and addr.email.strip().lower() == email
            for addr in sociallogin.email_addresses
        )
        if not provider_verified:
            return

        try:
            user = User.objects.get(email__iexact=email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return

        sociallogin.connect(request, user)
