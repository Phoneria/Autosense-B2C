from django.db import models

class Listing(models.Model):
    """İlan tekil kayıt — arabam.com scraper çıktısı."""
    # SQLite hiç zorlamıyordu (TEXT'e her uzunluk sığar) ama gerçek veride
    # 128'i aşan slug'lar var (en uzunu 170 karakter) -- Postgres migration'ı
    # bunu StringDataRightTruncation ile yakaladı. 255'e çıkarıldı, güvenli pay.
    id = models.CharField(primary_key=True, max_length=255)
    title = models.TextField()
    price = models.CharField(max_length=64)
    price_num = models.BigIntegerField(null=True, blank=True)  # numeric price for sorting
    address = models.TextField(blank=True, default="")
    date = models.CharField(max_length=64, blank=True, default="")
    seller_name = models.CharField(max_length=256, blank=True, default="")
    seller_type = models.CharField(max_length=64, blank=True, default="")
    phone = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")
    image_urls = models.TextField(blank=True, default="")  # JSON list of image URLs

    # Vehicle specs
    brand = models.CharField(max_length=64, blank=True, default="")
    model = models.CharField(max_length=128, blank=True, default="")
    km = models.IntegerField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    fuel = models.CharField(max_length=64, blank=True, default="")
    gear = models.CharField(max_length=64, blank=True, default="")
    color = models.CharField(max_length=64, blank=True, default="")
    body_type = models.CharField(max_length=64, blank=True, default="")
    engine_hp = models.IntegerField(null=True, blank=True)
    engine_cc = models.IntegerField(null=True, blank=True)

    # Analysis output fields (populated after bot run)
    estimated_value = models.BigIntegerField(null=True, blank=True)
    price_deviation_pct = models.FloatField(null=True, blank=True)
    opportunity_label = models.CharField(max_length=32, blank=True, default="")
    risk_score = models.FloatField(null=True, blank=True)
    confidence_pct = models.FloatField(null=True, blank=True)
    damage_score = models.FloatField(null=True, blank=True)
    damage_summary = models.CharField(max_length=64, blank=True, default="")
    ncap_score = models.FloatField(null=True, blank=True)

    arabam_url = models.URLField(max_length=512, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "search_listing"
