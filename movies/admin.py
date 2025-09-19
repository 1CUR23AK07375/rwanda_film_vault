from django.contrib import admin
from .models import Movie, Comment, WatchHistory, Visitor, ReactionTracker, DownloadHistory
from django.db.models import Sum  # ✅ add this import


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("movie", "user", "created_at")
    search_fields = ("movie__name", "user__username", "text")
    list_filter = ("created_at",)


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = (
        "ip_address", "country", "city", "lat", "lng",
        "first_visit", "last_visit", "known", "visit_count"
    )
    search_fields = ("ip_address", "country", "city")
    list_filter = ("known",)


@admin.register(WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ('movie', 'user', 'ip_address', 'start_time', 'end_time', 'duration', 'last_seen')
    list_filter = ('movie', 'user', 'start_time', 'end_time')
    search_fields = ('movie__name', 'user__username', 'ip_address')
    readonly_fields = ('duration', 'last_seen')


@admin.register(ReactionTracker)
class ReactionTrackerAdmin(admin.ModelAdmin):
    list_display = ("movie", "reaction_type", "ip_address", "reacted_at")
    list_filter = ("reaction_type", "reacted_at")
    search_fields = ("movie__name", "ip_address")


@admin.register(DownloadHistory)
class DownloadHistoryAdmin(admin.ModelAdmin):
    list_display = ("movie", "user", "ip_address", "downloaded_at")
    list_filter = ("movie", "downloaded_at")
    search_fields = ("movie__name", "user__username", "ip_address")


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("name", "download_count", "uploaded_at")
    ordering = ("-download_count", "-uploaded_at")
    search_fields = ("name",)

    def changelist_view(self, request, extra_context=None):
        # compute values for the dashboard
        total = Movie.objects.aggregate(total=Sum("download_count"))["total"] or 0
        top = Movie.objects.order_by("-download_count").first()
        latest = Movie.objects.order_by("-uploaded_at").first()

        extra = {
            "total_downloads": total,
            "top_movie": top,
            "latest_movie": latest,
        }
        if extra_context:
            extra.update(extra_context)

        # call the default changelist with our extra context
        return super().changelist_view(request, extra_context=extra)