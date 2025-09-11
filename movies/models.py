from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


# -------------------------------
# Movie model
# -------------------------------
class Movie(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    image_url = models.URLField(max_length=500, blank=True, null=True)
    video_url = models.URLField(max_length=500, blank=True, null=True)
    download_url = models.URLField(max_length=500, blank=True, null=True)
    # NEW: total views counter
    total_views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


# -------------------------------
# Reaction Tracker model
# -------------------------------
class ReactionTracker(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="reactions")
    ip_address = models.GenericIPAddressField()
    reaction_type = models.CharField(max_length=20)  # like, love, green_heart, fire
    reacted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("movie", "ip_address", "reaction_type")


# -------------------------------
# Comment model
# -------------------------------
class Comment(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="comment_set")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Optional guest name for unauthenticated commenters
    guest_name = models.CharField(max_length=80, blank=True, null=True, default="")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def display_name(self) -> str:
        """Prefer authenticated username; else guest_name; else 'Guest'."""
        if self.user:
            return self.user.username
        return self.guest_name or "Guest"

    def __str__(self):
        return f"{self.display_name()} on {self.movie.name}"


# -------------------------------
# Watch History model
# -------------------------------
class WatchHistory(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="watch_history")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)

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


# -------------------------------
# Visitor model
# -------------------------------
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

    def __str__(self):
        return f"{self.ip_address} ({'Known' if self.known else 'Guest'})"

    @property
    def is_online(self):
        """Visitor is considered online if seen within last 5 minutes."""
        return (timezone.now() - self.last_visit).total_seconds() < 300
