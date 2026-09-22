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
    plan = models.CharField(max_length=20, default="basic")
    credits = models.PositiveIntegerField(default=3)
    extra_credits = models.PositiveIntegerField(default=0)
    period_start = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)
