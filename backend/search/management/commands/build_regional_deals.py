from django.core.management.base import BaseCommand

from search.services import regional


class Command(BaseCommand):
    help = "Bölgesel fırsatlar tablosunu en son galeri snapshot'ından yeniden hesaplar."

    def handle(self, *args, **options):
        data = regional.get(force=True)
        self.stdout.write(self.style.SUCCESS(
            f"{data.get('snapshot_date')}: {data.get('priced_listings')} ilan fiyatlandı, {len(data.get('cities', []))} şehir."
        ))
