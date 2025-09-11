from django.contrib import admin
from .models import Movie, Comment, WatchHistory, Visitor

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("name", "uploaded_at")
    search_fields = ("name",)
    fields = ("name", "description", "image_url", "video_url", "download_url")

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("movie", "user", "created_at")
    search_fields = ("movie__name", "user__username", "text")
    list_filter = ("created_at",)
    
@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "country", "city", "lat", "lng", "first_visit", "last_visit", "known")
    search_fields = ("ip_address", "country", "city")
    list_filter = ("known",)


@admin.register(WatchHistory)
class WatchHistoryAdmin(admin.ModelAdmin):
    list_display = ('movie', 'user', 'ip_address', 'start_time', 'end_time', 'duration', 'last_seen')
    list_filter = ('movie', 'user', 'start_time', 'end_time')
    search_fields = ('movie__name', 'user__username', 'ip_address')
    readonly_fields = ('duration', 'last_seen')
