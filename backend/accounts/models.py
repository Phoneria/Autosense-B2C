from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

class UserManager(BaseUserManager):
    use_in_migrations = True
    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().lower()
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("E-posta gereklidir")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()
    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="b2c_user_email_ci_unique")]
        verbose_name = "kullanıcı"
        verbose_name_plural = "kullanıcılar"
    def save(self, *args, **kwargs):
        self.email = UserManager.normalize_email(self.email)
        super().save(*args, **kwargs)


class Subscription(models.Model):
    """Kullanıcının planı ve kredi bakiyesi.

    Ödeme sistemi henüz yok: plan seçimi ve kredi ekleme anında onaylanır.
    Plan kredileri her `billing.RESET_INTERVAL` sonunda plan kotasına
    yeniden doldurulur; sonradan eklenen kredi (`extra_credits`) sıfırlanmaz.
    """
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField("plan", max_length=20, default="basic")
    credits = models.PositiveIntegerField("kalan kredi", default=3)
    extra_credits = models.PositiveIntegerField("ek kredi", default=0)
    period_start = models.DateTimeField("dönem başlangıcı")
    updated_at = models.DateTimeField("son güncelleme", auto_now=True)

    class Meta:
        verbose_name = "üyelik"
        verbose_name_plural = "üyelikler"

    def __str__(self):
        return f"{self.user} ({self.plan})"


class PlanChange(models.Model):
    """Plan geçmişi: her plan değişikliği bir satır. Yönetim panelinde gösterilir."""
    SOURCE_CHOICES = [
        ("user", "Kullanıcı"),
        ("admin", "Yönetici"),
        ("payment", "Ödeme"),
        ("system", "Sistem"),
    ]
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="plan_changes")
    old_plan = models.CharField("eski plan", max_length=20, blank=True)
    new_plan = models.CharField("yeni plan", max_length=20)
    source = models.CharField("kaynak", max_length=10, choices=SOURCE_CHOICES, default="user")
    changed_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+", verbose_name="değiştiren")
    note = models.CharField("not", max_length=200, blank=True)
    created_at = models.DateTimeField("tarih", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "plan değişikliği"
        verbose_name_plural = "plan geçmişi"

    def __str__(self):
        return f"{self.user} {self.old_plan or '-'} → {self.new_plan}"


class UsageEvent(models.Model):
    """Kullanım kaydı: başarılı her analiz bir satır (kimin ne kadar aktif olduğunu görmek için)."""
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="usage_events")
    kind = models.CharField("tür", max_length=20, default="analysis")
    plan = models.CharField("o anki plan", max_length=20, blank=True)
    created_at = models.DateTimeField("tarih", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "kullanım kaydı"
        verbose_name_plural = "kullanım kayıtları"
        indexes = [models.Index(fields=["user", "created_at"])]


class PaidSubscription(models.Model):
    """iyzico üzerinden alınan ücretli abonelik (her ödeme denemesi bir kayıt).

    `paid_until`: son başarılı ödemenin kapsadığı dönemin sonu. Abonelik iptal
    edilse bile kullanıcı bu tarihe kadar planını kullanır.
    """
    STATUS_CHOICES = [(s, s) for s in ("PENDING", "ACTIVE", "UNPAID", "CANCELED", "EXPIRED", "FAILED")]
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="paid_subscriptions")
    plan = models.CharField(max_length=20)
    token = models.CharField(max_length=128, unique=True, null=True, blank=True)
    reference_code = models.CharField(max_length=64, unique=True, null=True, blank=True)
    customer_reference_code = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PENDING")
    paid_until = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]


class PaymentEvent(models.Model):
    """iyzico bildirimlerinin ham kaydı (aynı bildirim iki kez işlenmesin)."""
    iyzi_reference_code = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=64)
    subscription_reference_code = models.CharField(max_length=64, blank=True, default="")
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
