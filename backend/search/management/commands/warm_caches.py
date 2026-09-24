import json

from django.core.management.base import BaseCommand

from search.services import guide, regional


class Command(BaseCommand):
    help = ("Araç Rehberi ve Bölgesel Fırsatlar önbelleklerini açılışta hazırlar. "
            "Önbellek dosyası güncel snapshot'a aitse yeniden hesaplamaz.")

    def handle(self, *args, **options):
        latest = guide._latest_snapshot()
        latest = str(latest)[:10] if latest else None
        path = guide._cache_path()
        cached = None
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8")).get("snapshot_date")
            except (OSError, ValueError):
                cached = None
        if cached != latest:
            data = guide.rebuild()
            self.stdout.write(f"Araç rehberi hesaplandı: {data.get('snapshot_date')}")
        else:
            self.stdout.write(f"Araç rehberi önbellekte güncel: {cached}")
        data = regional.get()
        self.stdout.write(f"Bölgesel fırsatlar hazır: {data.get('snapshot_date')}")
