from django.core.management.base import BaseCommand

from search.services import guide


class Command(BaseCommand):
    help = "Araç Rehberi verisini galeri snapshot'larından yeniden hesaplar."

    def handle(self, *args, **options):
        data = guide.rebuild()
        self.stdout.write(self.style.SUCCESS(f"{data.get('snapshot_date')}: {len(data.get('models', {}))} model."))
