# movies/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ============================
    # Public Pages
    # ============================
    path("", views.home, name="home"),
    path("watch/<int:movie_id>/", views.watch_movie, name="watch_movie"),
    path("download/<int:movie_id>/", views.download_movie, name="download_movie"),

    # ============================
    # Comments APIs
    # ============================
    path("watch/<int:movie_id>/comments/", views.comments_feed, name="comments_feed"),
    path("comment_count/<int:movie_id>/", views.comment_count_api, name="comment_count_api"),

    # ============================
    # Viewers / Watch History APIs
    # ============================
    path("watch/<int:movie_id>/viewers/", views.real_time_viewers, name="real_time_viewers"),
    path("watch/start/<int:movie_id>/", views.start_watch, name="start_watch"),
    path("watch/stop/<int:watch_id>/", views.stop_watch, name="stop_watch"),

    # ============================
    # Admin Dashboard
    # ============================
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),

    # Admin Dashboard Data APIs
    path("api/visitor-stats/", views.visitor_stats_api, name="visitor_stats_api"),
    path("api/visitor-chart/", views.visitor_chart_data, name="visitor_chart_data"),
    path("api/visitor-country/", views.visitor_country_data, name="visitor_country_data"),
    path("api/visitor-map/", views.visitor_map_data, name="visitor_map_data"),
    path('search_suggestions/', views.search_suggestions, name='search_suggestions'),
    path('latest/', views.latest_movies, name='latest_movies'),

]
