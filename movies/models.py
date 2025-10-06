from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# ===============================
# Genre model
# ===============================
class Genre(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ===============================
# Movie model
# ===============================
class Movie(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    image_url = models.URLField(max_length=500, blank=True, null=True)
    video_url = models.URLField(max_length=500, blank=True, null=True)
    download_url = models.URLField(max_length=500, blank=True, null=True)

    # counters
    total_views = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["uploaded_at"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name

    def recalc_counters_from_history(self):
        """
        Recalculate total_views and download_count from related history tables.
        Useful for consistency checks or admin commands.
        """
        views = self.watch_history.count()
        downloads = self.download_history.count()

        update_fields = []
        if self.total_views != views:
            self.total_views = views
            update_fields.append("total_views")
        if self.download_count != downloads:
            self.download_count = downloads
            update_fields.append("download_count")

        if update_fields:
            self.save(update_fields=update_fields)

        return views, downloads


# ===============================
# Comment model
# ===============================
class Comment(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="comment_set")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    guest_name = models.CharField(max_length=80, blank=True, null=True, default="")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def display_name(self) -> str:
        if self.user:
            return self.user.username
        return self.guest_name or "Guest"

    def __str__(self):
        return f"{self.display_name()} on {self.movie.name}"


# ===============================
# Watch History model
# ===============================
class WatchHistory(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="watch_history")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen"]
        indexes = [
            models.Index(fields=["last_seen"]),
        ]

    def __str__(self):
        return f"{self.user.username if self.user else self.ip_address} - {self.movie.name}"

    @staticmethod
    def active_viewers(movie, window_seconds=60):
        """
        Count how many people are actively watching this movie.
        Anyone with a last_seen in the last `window_seconds` is considered live.
        """
        cutoff = timezone.now() - timedelta(seconds=window_seconds)
        return WatchHistory.objects.filter(movie=movie, last_seen__gte=cutoff).count()


# ===============================
# Download History model
# ===============================
class DownloadHistory(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="download_history")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-downloaded_at"]
        indexes = [
            models.Index(fields=["downloaded_at"]),
        ]

    def __str__(self):
        return f"{self.movie.name} download @ {self.downloaded_at}"


# ===============================
# Visitor model
# ===============================
class Visitor(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    lat = models.FloatField(default=0.0)
    lng = models.FloatField(default=0.0)

    first_visit = models.DateTimeField(auto_now_add=True)
    last_visit = models.DateTimeField(auto_now=True)

    known = models.BooleanField(default=False)
    visit_count = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-last_visit"]
        indexes = [
            models.Index(fields=["last_visit"]),
        ]

    def __str__(self):
        return f"{self.ip_address} ({'Known' if self.known else 'Guest'})"

    @property
    def is_online(self) -> bool:
        """
        Visitor is considered online if seen within last 5 minutes.
        """
        return (timezone.now() - self.last_visit).total_seconds() < 300
