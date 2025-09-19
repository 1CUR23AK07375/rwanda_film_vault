from django.core.management.base import BaseCommand
from django.db.models import Count
from movies.models import Movie, WatchHistory, DownloadHistory

class Command(BaseCommand):
    help = "Recalculate/populate Movie.total_views and Movie.download_count from history tables."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show changes without saving')
        parser.add_argument('--movie-id', type=int, help='Only recalc for a specific movie id')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        movie_id = options.get('movie_id')

        # aggregate watch counts
        watch_counts = WatchHistory.objects.values('movie').annotate(cnt=Count('id'))
        watch_map = {w['movie']: w['cnt'] for w in watch_counts}

        # aggregate download counts
        dl_counts = DownloadHistory.objects.values('movie').annotate(cnt=Count('id'))
        dl_map = {d['movie']: d['cnt'] for d in dl_counts}

        qs = Movie.objects.all()
        if movie_id:
            qs = qs.filter(id=movie_id)

        changed = 0
        for m in qs:
            new_views = watch_map.get(m.id, 0)
            new_downloads = dl_map.get(m.id, 0)
            if m.total_views != new_views or m.download_count != new_downloads:
                changed += 1
                if dry_run:
                    self.stdout.write(f"[DRY] Movie {m.id} '{m.name}': views {m.total_views} -> {new_views}, downloads {m.download_count} -> {new_downloads}")
                else:
                    m.total_views = new_views
                    m.download_count = new_downloads
                    m.save(update_fields=['total_views', 'download_count'])
                    self.stdout.write(f"Updated Movie {m.id} '{m.name}': views -> {new_views}, downloads -> {new_downloads}")

        self.stdout.write(self.style.SUCCESS(f"Done. Movies changed: {changed}"))
