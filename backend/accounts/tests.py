import re
import time
from urllib.parse import unquote
from unittest.mock import patch
from django.conf import settings
from django.test import TestCase, Client, override_settings
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from allauth.account.models import EmailAddress
from .models import User

PASSWORD = "Strong-test-pass-937!"
AUTH = "/_allauth/browser/v1/auth/"

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.token = self.client.get("/api/b2c/csrf").json()["csrfToken"]
    def post(self, route, data, client=None):
        c = client or self.client
        token = c.get("/api/b2c/csrf").json()["csrfToken"]
        return c.post(route, data, content_type="application/json", HTTP_X_CSRFTOKEN=token)
    def signup(self, email="hello@example.com"):
        return self.post(AUTH+"signup", {"email":email, "password":PASSWORD})
    def code(self):
        return re.search(r"^\s*(\d{6})\s*$", mail.outbox[-1].body, re.MULTILINE)[1]
    def verify(self):
        code = self.code()
        return self.post(AUTH+"email/verify", {"key":code}), code
    def logout(self):
        token = self.client.get("/api/b2c/csrf").json()["csrfToken"]
        return self.client.delete(AUTH+"session", HTTP_X_CSRFTOKEN=token)
    def verified_user(self):
        self.assertEqual(self.signup().status_code, 401)
        response, _ = self.verify()
        # Entering the code completes the pending login; tests continue signed out.
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.logout().status_code, 401)
        return User.objects.get()
    def test_complete_signup_verify_login_logout_and_cache(self):
        self.assertEqual(self.signup("Hello@Example.com").status_code, 401)
        self.assertEqual(User.objects.get().email, "hello@example.com")
        self.assertEqual(self.client.get("/api/b2c/me").status_code, 401)
        response, key = self.verify()
        # The code is entered by the session that supplied the password, so allauth
        # finishes the pending login with it instead of asking for the password again.
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["meta"]["is_authenticated"])
        self.assertEqual(self.client.get("/api/b2c/me").json()["email"], "hello@example.com")
        self.assertEqual(self.post(AUTH+"email/verify", {"key":key}).status_code, 409)
        self.assertEqual(self.logout().status_code, 401)
        self.assertEqual(self.client.get("/api/b2c/me").status_code, 401)
        self.assertEqual(self.post(AUTH+"login", {"email":"HELLO@example.com", "password":PASSWORD}).status_code, 200)
        me = self.client.get("/api/b2c/me")
        self.assertEqual(me.json()["email"], "hello@example.com")
        self.assertTrue(me.json()["features"]["analysis"])
        self.assertIn("no-store", me["Cache-Control"])
        token = self.client.get("/api/b2c/csrf").json()["csrfToken"]
        cookie = self.client.cookies["b2c_sessionid"].value
        self.assertEqual(self.client.delete(AUTH+"session", HTTP_X_CSRFTOKEN=token).status_code, 401)
        self.client.cookies["b2c_sessionid"] = cookie
        self.assertEqual(self.client.get("/api/b2c/me").status_code, 401)
    def test_csrf_on_every_anonymous_write(self):
        for route in ["signup", "login", "email/verify", "password/request", "password/reset"]:
            response = self.client.post(AUTH+route, {}, content_type="application/json")
            self.assertEqual(response.status_code, 403, route)
        self.assertEqual(self.client.post("/api/b2c/email/verification/request", {}).status_code, 403)
    def test_unverified_and_inactive_session_rejected(self):
        user = User.objects.create_user("blocked@example.com", PASSWORD)
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
        self.client.force_login(user, backend="allauth.account.auth_backends.AuthenticationBackend")
        self.assertEqual(self.client.get("/api/b2c/me").status_code, 403)
        EmailAddress.objects.update(verified=True)
        user.is_active=False
        user.save()
        self.assertEqual(self.client.get("/api/b2c/me").status_code, 401)
    def test_duplicate_normalized_and_database_constraint(self):
        self.signup()
        cache.clear()
        other = Client(enforce_csrf_checks=True)
        result = self.post(AUTH+"signup", {"email":"HELLO@EXAMPLE.COM", "password":PASSWORD}, other)
        self.assertEqual(result.status_code, 400, result.content)
        self.assertEqual([e["code"] for e in result.json()["errors"]], ["email_taken"])
        self.assertEqual(User.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="HELLO@EXAMPLE.COM", password="!")])
    def test_expired_verification_code(self):
        self.signup()
        code = self.code()
        expired = time.time() + settings.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT + 1
        with patch("allauth.account.internal.flows.code_verification.time.time", return_value=expired):
            response = self.post(AUTH+"email/verify", {"key":code})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(EmailAddress.objects.get().verified)

    def test_wrong_code_is_rejected_and_attempts_are_capped(self):
        self.signup()
        code = self.code()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(settings.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS - 1):
            response = self.post(AUTH+"email/verify", {"key":wrong})
            self.assertEqual(response.status_code, 400, response.content)
            self.assertEqual([e["code"] for e in response.json()["errors"]], ["incorrect_code"])
        # The final failure aborts the process, so the real code no longer works.
        self.post(AUTH+"email/verify", {"key":wrong})
        self.assertEqual(self.post(AUTH+"email/verify", {"key":code}).status_code, 409)
        self.assertFalse(EmailAddress.objects.get().verified)
    def test_resend_generic_and_rate_limited(self):
        route = "/api/b2c/email/verification/request"
        first=self.post(route, {"email":"missing@example.com"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.post(route, {"email":"missing@example.com"}).status_code, 429)
        self.signup()
        cache.clear()
        count=len(mail.outbox)
        response=self.post(route, {"email":"hello@example.com"})
        self.assertEqual(first.json(), response.json())
        self.assertEqual(len(mail.outbox), count+1)
    def test_password_reset_invalidates_sessions_and_key(self):
        self.verified_user()
        self.post(AUTH+"login", {"email":"hello@example.com", "password":PASSWORD})
        old_cookie=self.client.cookies["b2c_sessionid"].value
        other=Client(enforce_csrf_checks=True)
        response=self.post(AUTH+"password/request", {"email":"hello@example.com"}, other)
        self.assertEqual(response.status_code, 200, response.content)
        key=unquote(re.search(r"/reset-password/(\S+)", mail.outbox[-1].body)[1])
        response=self.post(AUTH+"password/reset", {"key":key, "password":"New-safe-password-624!"}, other)
        self.assertEqual(response.status_code, 401, response.content)
        self.client.cookies["b2c_sessionid"]=old_cookie
        self.assertEqual(self.client.get("/api/b2c/me").status_code, 401)
        self.assertEqual(self.post(AUTH+"password/reset", {"key":key, "password":PASSWORD}, other).status_code, 400)
    def test_route_isolation(self):
        for path in ["/api/token/", "/api/accounts/login/", "/admin/", "/accounts/login/", "/_allauth/app/v1/auth/session"]:
            self.assertEqual(self.client.get(path).status_code, 404, path)


    def test_competing_signup_after_validation_is_generic(self):
        from allauth.headless.account.inputs import SignupInput
        original = SignupInput.try_save
        def competing_save(form, request):
            user = User.objects.create_user(form.cleaned_data["email"], PASSWORD)
            EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
            return original(form, request)
        with patch.object(SignupInput, "try_save", competing_save):
            response = self.signup()
        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(User.objects.count(), 1)

    def test_login_throttle_and_unknown_feature(self):
        from .features import has_feature
        user = self.verified_user()
        self.assertFalse(has_feature(user, "premium"))
        with override_settings(ACCOUNT_RATE_LIMITS={"login":"1/m/ip"}):
            self.post(AUTH+"login", {"email":user.email,"password":"wrong"})
            response=self.post(AUTH+"login", {"email":user.email,"password":"wrong"})
            self.assertEqual(response.status_code, 429)

    def test_expired_password_reset(self):
        from datetime import datetime, timedelta
        self.verified_user()
        self.post(AUTH+"password/request", {"email":"hello@example.com"})
        key=unquote(re.search(r"/reset-password/(\S+)", mail.outbox[-1].body)[1])
        with patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now", return_value=datetime.now()+timedelta(hours=2)):
            response=self.post(AUTH+"password/reset", {"key":key,"password":"Some-other-password-934!"})
        self.assertEqual(response.status_code, 400)
