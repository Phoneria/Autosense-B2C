"""Yönetim paneli: erişim, liste/özet, CSV, plan geçmişi, kullanım kaydı, giriş sınırlaması."""
import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from accounts import billing
from accounts.admin import site
from accounts.models import PlanChange, Subscription, UsageEvent, User

PW = "Admin-strong-pass-9137!"


@pytest.fixture
def admin_user(db):
    cache.clear()
    return User.objects.create_superuser("yonetici@example.com", PW)


@pytest.fixture
def members(db):
    out = []
    for i, plan in enumerate(["basic", "pro", "premium"]):
        u = User.objects.create_user(f"uye{i}@example.com", "Long-strong-test-472!")
        EmailAddress.objects.create(user=u, email=u.email, verified=(i != 0), primary=True)
        billing.status(u)
        billing.choose_plan(u, plan)
        out.append(u)
    return out


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.force_login(admin_user)
    return c


def test_normal_kullanici_panele_giremez(db, members):
    c = Client()
    c.force_login(members[0])
    r = c.get("/admin/")
    assert r.status_code == 302 and "/admin/login/" in r["Location"]


def test_giris_sayfasi_ve_statik_dosyalar(db):
    r = Client().get("/admin/login/")
    assert r.status_code == 200 and "AutoSense Yönetim" in r.content.decode()


def test_ozet_ve_kullanici_listesi(admin_client, members):
    r = admin_client.get("/admin/")
    body = r.content.decode()
    assert r.status_code == 200 and "Toplam kullanıcı" in body and "Plan: Premium" in body and "Son plan değişiklikleri" in body
    r = admin_client.get(reverse("admin:accounts_user_changelist"))
    body = r.content.decode()
    assert r.status_code == 200
    for u in members:
        assert u.email in body
    r = admin_client.get(reverse("admin:accounts_user_changelist") + "?plan=premium")
    body = r.content.decode()
    assert "uye2@example.com" in body and "uye0@example.com" not in body
    r = admin_client.get(reverse("admin:accounts_user_changelist") + "?dogrulandi=hayir")
    body = r.content.decode()
    assert "uye0@example.com" in body and "uye1@example.com" not in body


def test_kullanici_detay_sayfasi(admin_client, members):
    r = admin_client.get(reverse("admin:accounts_user_change", args=[members[1].pk]))
    assert r.status_code == 200 and "plan geçmişi" in r.content.decode().lower()


def test_kullanici_plan_secince_gecmise_yazilir(db, members):
    pc = PlanChange.objects.filter(user=members[2]).first()
    assert pc.old_plan == "basic" and pc.new_plan == "premium" and pc.source == "user"
    assert not PlanChange.objects.filter(user=members[0]).exists()  # basic -> basic değişiklik değil


def test_panelden_plan_degisince_gecmise_yonetici_yazilir(admin_client, admin_user, members):
    u = members[0]
    sub = Subscription.objects.get(user=u)
    url = reverse("admin:accounts_user_change", args=[u.pk])
    data = {
        "email": u.email, "first_name": "", "last_name": "", "is_active": "on",
        "date_joined_0": "", "last_login_0": "",
        "subscription-TOTAL_FORMS": "1", "subscription-INITIAL_FORMS": "1",
        "subscription-MIN_NUM_FORMS": "0", "subscription-MAX_NUM_FORMS": "1",
        "subscription-0-id": str(sub.pk), "subscription-0-user": str(u.pk),
        "subscription-0-plan": "pro", "subscription-0-credits": "3",
        "plan_changes-TOTAL_FORMS": "0", "plan_changes-INITIAL_FORMS": "0",
        "plan_changes-MIN_NUM_FORMS": "0", "plan_changes-MAX_NUM_FORMS": "1000",
    }
    r = admin_client.post(url, data)
    assert r.status_code == 302, r.content.decode()[:2000]
    sub.refresh_from_db()
    assert sub.plan == "pro" and sub.credits == billing.PLANS["pro"]["credits"]
    pc = PlanChange.objects.filter(user=u).first()
    assert (pc.old_plan, pc.new_plan, pc.source, pc.changed_by) == ("basic", "pro", "admin", admin_user)


def test_disa_aktarim_excel_ve_csv(admin_client, members):
    UsageEvent.objects.create(user=members[1], plan="pro")
    url = reverse("admin:accounts_user_changelist")
    ids = [u.pk for u in members]
    r = admin_client.post(url, {"action": "export_admin_action", "_selected_action": ids})
    assert r.status_code == 200 and "E-posta" in r.content.decode()
    from import_export.formats.base_formats import CSV, XLSX
    from accounts.admin import UserResource
    data = UserResource().export(User.objects.filter(pk__in=ids).select_related("subscription"))
    assert "uye1@example.com" in data.csv and "Pro" in data.csv
    assert XLSX().export_data(data)[:2] == b"PK"


def test_gecmis_ve_kullanim_salt_okunur(admin_client, members):
    for name in ("planchange", "usageevent"):
        assert admin_client.get(reverse(f"admin:accounts_{name}_changelist")).status_code == 200
        assert admin_client.get(reverse(f"admin:accounts_{name}_add")).status_code == 403


def test_hatali_girisler_sinirlanir(admin_user, settings):
    settings.ADMIN_LOGIN_MAX_FAILURES = 3
    c = Client()
    for _ in range(3):
        r = c.post("/admin/login/", {"username": admin_user.email, "password": "yanlis"})
        assert r.status_code == 200
    r = c.post("/admin/login/", {"username": admin_user.email, "password": PW})
    assert r.status_code == 429


def test_dogru_sifreyle_giris(admin_user):
    c = Client()
    r = c.post("/admin/login/?next=/admin/", {"username": admin_user.email, "password": PW})
    assert r.status_code == 302 and r["Location"] == "/admin/"


def test_hesap_basina_deneme_siniri(admin_user, settings):
    """Farklı IP'lerden gelen denemeler de aynı hesap için sayılır."""
    settings.ADMIN_LOGIN_MAX_FAILURES = 100
    settings.ADMIN_LOGIN_MAX_FAILURES_PER_ACCOUNT = 3
    for i in range(3):
        r = Client(HTTP_X_FORWARDED_FOR=f"10.0.0.{i}").post(
            "/admin/login/", {"username": admin_user.email.upper(), "password": "yanlis"})
        assert r.status_code == 200
    r = Client(HTTP_X_FORWARDED_FOR="10.0.0.99").post("/admin/login/", {"username": admin_user.email, "password": PW})
    assert r.status_code == 429


def test_yonetici_oturumu_iki_saat(admin_client, settings, members):
    admin_client.get("/admin/")
    assert admin_client.session.get_expiry_age() == settings.ADMIN_SESSION_SECONDS == 7200
    c = Client()
    c.force_login(members[0])            # normal üye: site oturumu süresi değişmez
    c.get("/admin/")
    assert c.session.get_expiry_age() == settings.SESSION_COOKIE_AGE
