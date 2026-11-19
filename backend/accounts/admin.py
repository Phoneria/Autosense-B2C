"""AutoSense yönetim paneli (/admin/) — Unfold arayüzü.

Kullanıcılar, üyelik planları, plan geçmişi ve kullanım kayıtları. Yalnız is_staff
hesaplar girebilir; hatalı girişler IP başına sınırlanır. Panelde yapılan her değişiklik
Django'nun işlem kaydında (LogEntry, "Geçmiş" düğmesi) tutulur.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.admin import SimpleListFilter, register
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from import_export import fields, resources
from import_export.admin import ExportActionModelAdmin
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.filters.admin import RangeDateFilter
from unfold.contrib.import_export.forms import ExportForm
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.sites import UnfoldAdminSite

from . import billing
from .models import PaidSubscription, PlanChange, Subscription, UsageEvent, User

PLAN_CHOICES = [(k, v["name"]) for k, v in billing.PLANS.items()]
PLAN_RENK = {"Basic": "info", "Pro": "warning", "Premium": "success", "—": "danger"}


def _client_ip(request) -> str:
    # Caddy arkasında: gerçek IP X-Forwarded-For'un ilk değeridir.
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd else "") or request.META.get("REMOTE_ADDR", "?")


def _plan_adi(user) -> str:
    sub = getattr(user, "subscription", None)
    return billing.PLANS.get(sub.plan, {}).get("name", sub.plan) if sub else "—"


def _ad(key: str) -> str:
    return billing.PLANS.get(key, {}).get("name", key) if key else "—"


def _kredi(user):
    sub = getattr(user, "subscription", None)
    if not sub:
        return "—"
    return "sınırsız" if billing.PLANS.get(sub.plan, {}).get("unlimited") else sub.credits


# ── Panel sitesi: giriş sınırlaması ve özet ekranı ───────────────────────
class AutoSenseAdminSite(UnfoldAdminSite):
    site_header = "AutoSense"
    site_title = "AutoSense Yönetim"
    index_title = "Genel bakış"
    index_template = "admin/autosense_index.html"

    def login(self, request, extra_context=None):
        """Hatalı giriş sınırı: IP başına ve hesap (e-posta) başına ayrı sayaç."""
        anahtarlar = [(f"admin-login-fail:{_client_ip(request)}", getattr(settings, "ADMIN_LOGIN_MAX_FAILURES", 8))]
        hesap = (request.POST.get("username") or "").strip().lower() if request.method == "POST" else ""
        if hesap:
            ozet_ = hashlib.sha256(hesap.encode()).hexdigest()[:32]
            anahtarlar.append((f"admin-login-fail-hesap:{ozet_}",
                               getattr(settings, "ADMIN_LOGIN_MAX_FAILURES_PER_ACCOUNT", 10)))
        if request.method == "POST" and any((cache.get(k) or 0) >= n for k, n in anahtarlar):
            return HttpResponse("Çok fazla hatalı giriş denemesi. Lütfen 15 dakika sonra tekrar deneyin.",
                                status=429, content_type="text/plain; charset=utf-8")
        response = super().login(request, extra_context)
        if request.method == "POST" and not request.user.is_authenticated:
            for k, _ in anahtarlar:
                try:
                    cache.incr(k)
                except ValueError:
                    cache.set(k, 1, getattr(settings, "ADMIN_LOGIN_BLOCK_SECONDS", 900))
        return response

    def index(self, request, extra_context=None):
        return super().index(request, {**(extra_context or {}), **ozet(request)})


def ozet(request) -> dict:
    """Özet ekranı verisi: KPI'lar, son 30 günün kayıt/analiz grafiği, plan dağılımı, son kayıtlar."""
    now = timezone.now()
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    users = User.objects.all()
    toplam = users.count()
    plan_say = dict(Subscription.objects.values_list("plan").annotate(n=Count("id")))

    gunler = [(today - timedelta(days=i)).date() for i in range(29, -1, -1)]
    bas = today - timedelta(days=29)
    kayit = dict(users.filter(date_joined__gte=bas).annotate(g=TruncDate("date_joined"))
                 .values_list("g").annotate(n=Count("id")))
    analiz = dict(UsageEvent.objects.filter(created_at__gte=bas).annotate(g=TruncDate("created_at"))
                  .values_list("g").annotate(n=Count("id")))
    grafik = {
        "labels": [g.strftime("%d.%m") for g in gunler],
        "datasets": [
            {"label": "Yeni kayıt", "data": [kayit.get(g, 0) for g in gunler],
             "backgroundColor": "var(--color-primary-600)", "borderRadius": 4},
            {"label": "Analiz", "data": [analiz.get(g, 0) for g in gunler],
             "backgroundColor": "var(--color-primary-300)", "borderRadius": 4},
        ],
    }
    kpis = [
        {"baslik": "Toplam kullanıcı", "deger": toplam, "alt": f"{users.filter(is_active=True).count()} aktif hesap",
         "link": reverse("admin:accounts_user_changelist")},
        {"baslik": "Son 30 günde yeni kayıt", "deger": users.filter(date_joined__gte=now - timedelta(days=30)).count(),
         "alt": f"Bugün {users.filter(date_joined__gte=today).count()}, son 7 gün "
                f"{users.filter(date_joined__gte=now - timedelta(days=7)).count()}",
         "link": reverse("admin:accounts_user_changelist")},
        {"baslik": "Son 7 günde aktif", "deger": UsageEvent.objects.filter(created_at__gte=now - timedelta(days=7))
                                                    .values("user").distinct().count(),
         "alt": "En az bir analiz yapan kullanıcı", "link": reverse("admin:accounts_usageevent_changelist")},
        {"baslik": "Bugünkü analiz", "deger": UsageEvent.objects.filter(created_at__gte=today).count(),
         "alt": f"Son 30 gün: {sum(analiz.values())}", "link": reverse("admin:accounts_usageevent_changelist")},
    ]
    planlar = []
    for key, name in PLAN_CHOICES:
        n = plan_say.get(key, 0)
        planlar.append({"ad": name, "sayi": n, "oran": round(n * 100 / toplam) if toplam else 0,
                        "link": reverse("admin:accounts_user_changelist") + f"?plan={key}"})
    son_kayitlar = [
        [u.email, _plan_adi(u), timezone.localtime(u.date_joined).strftime("%d.%m.%Y %H:%M")]
        for u in users.select_related("subscription").order_by("-date_joined")[:8]
    ]
    son_degisiklik = [
        [p.user.email, f"{_ad(p.old_plan)} → {_ad(p.new_plan)}", p.get_source_display(),
         timezone.localtime(p.created_at).strftime("%d.%m.%Y %H:%M")]
        for p in PlanChange.objects.select_related("user").order_by("-created_at")[:8]
    ]
    return {
        "as_kpis": kpis,
        "as_grafik": json.dumps(grafik),
        "as_planlar": planlar,
        "as_plansiz": users.filter(subscription__isnull=True).count(),
        "as_son_kayitlar": {"headers": ["E-posta", "Plan", "Kayıt"], "rows": son_kayitlar},
        "as_son_degisiklik": {"headers": ["E-posta", "Değişiklik", "Kaynak", "Tarih"], "rows": son_degisiklik},
    }


site = AutoSenseAdminSite(name="admin")


# ── Kullanıcılar ─────────────────────────────────────────────────────────
class SubscriptionForm(forms.ModelForm):
    plan = forms.ChoiceField(choices=PLAN_CHOICES, label="Plan")

    class Meta:
        model = Subscription
        fields = ("plan", "credits")


class SubscriptionInline(StackedInline):
    model = Subscription
    form = SubscriptionForm
    can_delete = False
    extra = 0
    max_num = 1
    fields = ("plan", "credits", "period_start", "updated_at")
    readonly_fields = ("period_start", "updated_at")
    verbose_name = "üyelik"
    verbose_name_plural = "üyelik"


class PlanChangeInline(TabularInline):
    model = PlanChange
    fk_name = "user"
    extra = 0
    can_delete = False
    fields = ("created_at", "old_plan", "new_plan", "source", "changed_by", "note")
    readonly_fields = fields
    verbose_name_plural = "plan geçmişi"

    def has_add_permission(self, request, obj=None):
        return False


class PlanFilter(SimpleListFilter):
    title = "plan"
    parameter_name = "plan"

    def lookups(self, request, model_admin):
        return PLAN_CHOICES + [("yok", "Plan kaydı yok")]

    def queryset(self, request, qs):
        if self.value() == "yok":
            return qs.filter(subscription__isnull=True)
        if self.value():
            return qs.filter(subscription__plan=self.value())
        return qs


class VerifiedFilter(SimpleListFilter):
    title = "e-posta doğrulandı"
    parameter_name = "dogrulandi"

    def lookups(self, request, model_admin):
        return [("evet", "Evet"), ("hayir", "Hayır")]

    def queryset(self, request, qs):
        q = Q(emailaddress__verified=True)
        if self.value() == "evet":
            return qs.filter(q).distinct()
        if self.value() == "hayir":
            return qs.exclude(q)
        return qs


class UserResource(resources.ModelResource):
    """Dışa aktarım (CSV / Excel) sütunları."""
    eposta = fields.Field(attribute="email", column_name="E-posta")
    ad = fields.Field(attribute="first_name", column_name="Ad")
    soyad = fields.Field(attribute="last_name", column_name="Soyad")
    plan = fields.Field(column_name="Plan")
    kredi = fields.Field(column_name="Kalan kredi")
    plan_baslangic = fields.Field(column_name="Plan başlangıcı")
    kayit = fields.Field(column_name="Kayıt tarihi")
    son_giris = fields.Field(column_name="Son giriş")
    dogrulandi = fields.Field(column_name="E-posta doğrulandı")
    analiz = fields.Field(column_name="Analiz sayısı")
    son_analiz = fields.Field(column_name="Son analiz")
    aktif = fields.Field(column_name="Aktif")

    class Meta:
        model = User
        fields = ("eposta", "ad", "soyad", "plan", "kredi", "plan_baslangic", "kayit", "son_giris",
                  "dogrulandi", "analiz", "son_analiz", "aktif")
        export_order = fields

    @staticmethod
    def _t(d):
        return timezone.localtime(d).strftime("%d.%m.%Y %H:%M") if d else ""

    def dehydrate_plan(self, u):
        return _plan_adi(u)

    def dehydrate_kredi(self, u):
        return _kredi(u)

    def dehydrate_plan_baslangic(self, u):
        sub = getattr(u, "subscription", None)
        return self._t(sub.period_start) if sub else ""

    def dehydrate_kayit(self, u):
        return self._t(u.date_joined)

    def dehydrate_son_giris(self, u):
        return self._t(u.last_login)

    def dehydrate_dogrulandi(self, u):
        return "Evet" if getattr(u, "_dog", 0) else "Hayır"

    def dehydrate_analiz(self, u):
        return getattr(u, "_analiz", 0)

    def dehydrate_son_analiz(self, u):
        return self._t(getattr(u, "_son", None))

    def dehydrate_aktif(self, u):
        return "Evet" if u.is_active else "Hayır"


@register(User, site=site)
class UserAdmin(BaseUserAdmin, ExportActionModelAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    resource_classes = [UserResource]
    export_form_class = ExportForm

    ordering = ("-date_joined",)
    list_display = ("email", "plan_rozeti", "kredi", "dogrulandi", "date_joined", "last_login",
                    "analiz_sayisi", "son_analiz", "is_active")
    list_filter = (PlanFilter, VerifiedFilter, "is_active", "is_staff", ("date_joined", RangeDateFilter))
    list_filter_submit = True
    search_fields = ("email", "first_name", "last_name")
    list_per_page = 50
    readonly_fields = ("date_joined", "last_login")
    inlines = [SubscriptionInline, PlanChangeInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Kişisel bilgiler", {"fields": ("first_name", "last_name")}),
        ("Durum", {"fields": ("is_active",)}),
        ("Yönetim yetkileri", {"classes": ("collapse",),
                               "fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Tarihler", {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)

    def get_queryset(self, request):
        return (super().get_queryset(request).select_related("subscription")
                .annotate(_analiz=Count("usage_events", distinct=True),
                          _son=Max("usage_events__created_at"),
                          _dog=Count("emailaddress", filter=Q(emailaddress__verified=True), distinct=True)))

    @display(description="plan", ordering="subscription__plan", label=PLAN_RENK)
    def plan_rozeti(self, obj):
        return _plan_adi(obj)

    @display(description="kredi", ordering="subscription__credits")
    def kredi(self, obj):
        return _kredi(obj)

    @display(description="doğrulandı", boolean=True, ordering="_dog")
    def dogrulandi(self, obj):
        return bool(obj._dog)

    @display(description="analiz", ordering="_analiz")
    def analiz_sayisi(self, obj):
        return obj._analiz

    @display(description="son analiz", ordering="_son")
    def son_analiz(self, obj):
        return obj._son

    def save_formset(self, request, form, formset, change):
        """Panelden plan değişirse plan geçmişine 'Yönetici' kaynağıyla yazılır."""
        if formset.model is not Subscription:
            return super().save_formset(request, form, formset, change)
        with transaction.atomic():
            for f in formset.forms:
                if f.has_changed() and not f.instance.pk:   # yeni üyelik kaydı
                    f.instance.period_start = timezone.now()
                    f.instance.credits = billing.PLANS[f.cleaned_data.get("plan", "basic")]["credits"]
                    continue
                if not f.has_changed() or not f.instance.pk:
                    continue
                old = Subscription.objects.get(pk=f.instance.pk).plan
                new = f.cleaned_data.get("plan", old)
                if new != old:
                    sub = f.instance
                    sub.credits = billing.PLANS[new]["credits"]
                    sub.period_start = timezone.now()
                    PlanChange.objects.create(user=sub.user, old_plan=old, new_plan=new,
                                              source="admin", changed_by=request.user)
            super().save_formset(request, form, formset, change)
            for obj in formset.new_objects:
                PlanChange.objects.create(user=obj.user, old_plan="", new_plan=obj.plan,
                                          source="admin", changed_by=request.user)


@register(Group, site=site)
class GroupAdmin(ModelAdmin):
    search_fields = ("name",)


# ── Plan geçmişi ve kullanım (salt okunur) ───────────────────────────────
class ReadOnlyAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@register(PlanChange, site=site)
class PlanChangeAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "old_plan", "new_plan", "kaynak", "changed_by")
    list_filter = ("new_plan", "source", ("created_at", RangeDateFilter))
    list_filter_submit = True
    search_fields = ("user__email",)
    list_select_related = ("user", "changed_by")

    @display(description="kaynak", ordering="source",
             label={"Kullanıcı": "info", "Yönetici": "warning", "Ödeme": "success", "Sistem": "danger"})
    def kaynak(self, obj):
        return obj.get_source_display()


@register(UsageEvent, site=site)
class UsageEventAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "kind", "plan")
    list_filter = ("kind", "plan", ("created_at", RangeDateFilter))
    list_filter_submit = True
    search_fields = ("user__email",)
    list_select_related = ("user",)


@register(PaidSubscription, site=site)
class PaidSubscriptionAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "plan", "status", "paid_until", "reference_code")
    list_filter = ("status", "plan", ("created_at", RangeDateFilter))
    list_filter_submit = True
    search_fields = ("user__email", "reference_code")
    list_select_related = ("user",)
