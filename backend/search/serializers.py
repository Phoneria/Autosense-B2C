import math

from rest_framework import serializers


class FiniteFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail("invalid")
        return value


class VehicleSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=["otomobil", "arazi-suv-pick-up", "minivan-panelvan"], default="otomobil"
    )
    brand = serializers.CharField(max_length=100)
    series = serializers.CharField(max_length=150)
    engine = serializers.CharField(max_length=150)
    package = serializers.CharField(max_length=150, required=False, allow_null=True, allow_blank=True)


class DamageSerializer(serializers.Serializer):
    parca = serializers.ChoiceField(choices=[
        "Ön tampon", "Sol ön çamurluk", "Kaput", "Sağ ön çamurluk",
        "Sol ön kapı", "Tavan", "Sağ ön kapı", "Sol arka kapı", "Sağ arka kapı",
        "Sol arka çamurluk", "Sağ arka çamurluk", "Bagaj", "Arka tampon",
    ])
    durum = serializers.ChoiceField(choices=["Boyalı", "Lokal Boyalı", "Değişmiş", "Orijinal", "Belirtilmemiş"])


class AnalysisSerializer(VehicleSerializer):
    year = serializers.IntegerField(min_value=1950, max_value=2100)
    km = FiniteFloatField(min_value=0, max_value=10_000_000)
    price = FiniteFloatField(min_value=1, max_value=1_000_000_000)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    district = serializers.CharField(max_length=100, required=False, allow_blank=True)
    color = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    fuel = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    gear = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    agir_hasar = serializers.BooleanField(default=False)
    damage = DamageSerializer(many=True, required=False, max_length=13)
    description = serializers.CharField(max_length=50_000, required=False, allow_blank=True)


class ListingTextSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500_000, trim_whitespace=False)
