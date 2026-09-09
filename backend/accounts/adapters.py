from django.db import IntegrityError, transaction
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.internal.flows.signup import prevent_enumeration
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.headless.base.response import AuthenticationResponse

class AccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        return super().clean_email(email).strip().lower()

    def save_user(self, request, user, form, commit=True):
        try:
            with transaction.atomic():
                return super().save_user(request, user, form, commit=commit)
        except IntegrityError:
            # A competing signup can win after allauth validates the address.
            # Keep the database constraint authoritative without exposing it.
            if not type(user).objects.filter(email__iexact=form.cleaned_data["email"]).exists():
                raise
            response = prevent_enumeration(request, email=form.cleaned_data["email"])
            raise ImmediateHttpResponse(AuthenticationResponse.from_response(request, response))
