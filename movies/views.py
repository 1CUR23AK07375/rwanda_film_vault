from django.utils.timesince import timesince
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta

from .models import Movie, Comment, WatchHistory, Visitor
from .utils.ip_tracker import get_client_ip, get_geoip_location


# ==========================
# Home Page with Visitor Tracking
# ==========================
def home(request):
    # Track visits in session
    request.session['visits'] = request.session.get('visits', 0) + 1

    # Track visitor by IP
    ip = get_client_ip(request)
    visitor, created = Visitor.objects.get_or_create(ip_address=ip)

    # GeoIP info
    country, city, lat, lng = get_geoip_location(ip)
    visitor.country = country
    visitor.city = city
    visitor.lat = lat
    visitor.lng = lng
    visitor.last_visit = timezone.now()
    visitor.visit_count = visitor.visit_count + 1 if not created else 1
    visitor.save(update_fields=[
        "country", "city", "lat", "lng", "last_visit", "visit_count"
    ])

    # Search / list movies
    query = request.GET.get('q', '').strip()
    movies = (
        Movie.objects.filter(Q(name__icontains=query)).order_by('-uploaded_at')
        if query else Movie.objects.all().order_by('-uploaded_at')
    )

    return render(request, 'movies/home.html', {
        'movies': movies,
        'session_visits': request.session['visits'],
    })


# ==========================
# Watch Movie + Comments
# ==========================
def watch_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    # Latest comment id (for AJAX polling)
    last_comment = movie.comment_set.order_by('-id').first()
    last_comment_id = last_comment.id if last_comment else 0

    if request.method == "POST":
        text = (request.POST.get("text") or "").strip()
        provided_name = (request.POST.get("guest_name") or "").strip()

        if text:
            comment = Comment.objects.create(
                movie=movie,
                user=request.user if request.user.is_authenticated else None,
                guest_name=provided_name if provided_name else None,
                text=text,
            )

            # AJAX response for comment post
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "count": movie.comment_set.count(),
                    "latest_comment": {
                        "id": comment.id,
                        "guest_name": comment.guest_name or "",
                        "user": comment.user.username if comment.user else None,
                        "text": comment.text,
                        "created_at": timesince(comment.created_at) + " ago",
                    }
                })

            return redirect("watch_movie", movie_id=movie.id)

    # **NOTE**: show ALL comments (no [:20] slice) - ordering newest-first
    comments = movie.comment_set.select_related('user').order_by('-id')

    # total views = every watch_history record counts (option 1 — count each play)
    total_views = WatchHistory.objects.filter(movie=movie).count()

    # live viewers snapshot (same logic used by real_time_viewers)
    active_window = timezone.now() - timedelta(minutes=10)
    live_viewers = WatchHistory.objects.filter(
        movie=movie, end_time__isnull=True, start_time__gte=active_window
    ).count()

    return render(request, "movies/watch_movie.html", {
        "movie": movie,
        "comments": comments,
        "last_comment_id": last_comment_id,
        "total_views": total_views,
        "live_viewers": live_viewers,
    })


# ==========================
# Comments feed for polling (AJAX)
# Returns comments newer than ?since=<last_id>
# Includes comment count, total_views and live_viewers for UI updates
# ==========================
def comments_feed(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    try:
        since_id = int(request.GET.get("since", "0"))
    except (TypeError, ValueError):
        since_id = 0

    qs = movie.comment_set.select_related('user').order_by("id")
    if since_id > 0:
        qs = qs.filter(id__gt=since_id)

    comments = [{
        "id": c.id,
        "guest_name": c.guest_name or "",
        "user": c.user.username if c.user else None,
        "text": c.text,
        "created_at_display": timesince(c.created_at) + " ago"
    } for c in qs]

    # Recompute total_views & live_viewers for each poll so UI stays in sync
    total_views = WatchHistory.objects.filter(movie=movie).count()
    active_window = timezone.now() - timedelta(minutes=10)
    live_viewers = WatchHistory.objects.filter(
        movie=movie, end_time__isnull=True, start_time__gte=active_window
    ).count()

    return JsonResponse({
        "comments": comments,
        "count": movie.comment_set.count(),
        "total_views": total_views,
        "live_viewers": live_viewers,
    })


# ==========================
# Real-Time Viewers API
# ==========================
def real_time_viewers(request, movie_id):
    active_window = timezone.now() - timedelta(minutes=10)
    active_sessions = WatchHistory.objects.filter(
        movie_id=movie_id,
        end_time__isnull=True,
        start_time__gte=active_window,
    ).count()
    return JsonResponse({"count": active_sessions})


# ==========================
# Download Movie
# ==========================
def download_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if not movie.download_url:
        return HttpResponse("No download link available for this movie.", status=404)
    return redirect(movie.download_url)


# ==========================
# Comment Count API
# ==========================
def comment_count_api(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    return JsonResponse({'count': movie.comment_set.count()})


# ==========================
# Watch History Tracking (start/stop)
# start_watch and stop_watch are csrf_exempt in your existing design
# ==========================
@csrf_exempt
def start_watch(request, movie_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    movie = get_object_or_404(Movie, id=movie_id)
    ip = get_client_ip(request)

    # Close dangling sessions for this IP+movie
    WatchHistory.objects.filter(
        movie=movie, ip_address=ip, end_time__isnull=True
    ).update(end_time=timezone.now())

    watch = WatchHistory.objects.create(
        movie=movie,
        user=request.user if request.user.is_authenticated else None,
        ip_address=ip,
        start_time=timezone.now(),
    )

    # Update visitor + geo
    visitor, _ = Visitor.objects.get_or_create(ip_address=ip)
    country, city, lat, lng = get_geoip_location(ip)
    visitor.country = country
    visitor.city = city
    visitor.lat = lat
    visitor.lng = lng
    visitor.last_visit = timezone.now()
    visitor.save(update_fields=["country", "city", "lat", "lng", "last_visit"])

    return JsonResponse({"watch_id": watch.id, "status": "started"})


@csrf_exempt
def stop_watch(request, watch_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        watch = WatchHistory.objects.get(id=watch_id)
    except WatchHistory.DoesNotExist:
        return JsonResponse({"error": "Watch session not found"}, status=404)

    if watch.end_time is None:
        watch.end_time = timezone.now()
        if watch.start_time:
            watch.duration = watch.end_time - watch.start_time
        watch.save(update_fields=["end_time", "duration"])

    formatted_duration = "00:00:00"
    if watch.duration:
        total_seconds = int(watch.duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        formatted_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return JsonResponse({"status": "stopped", "duration": formatted_duration})


# ==========================
# Admin Dashboard + Dashboard APIs (unchanged)
# ==========================
def admin_dashboard(request):
    return render(request, 'movies/admin_dashboard.html', {})


def _compute_online_from_last_watch(last_watch):
    if not last_watch:
        return False
    recently = last_watch.start_time and (timezone.now() - last_watch.start_time) <= timedelta(minutes=10)
    return last_watch.end_time is None and recently


def visitor_stats_api(request):
    visitors = Visitor.objects.all().order_by('-last_visit')
    rows = []
    for v in visitors:
        last_watch = WatchHistory.objects.filter(ip_address=v.ip_address) \
                                         .select_related('movie') \
                                         .order_by('-start_time').first()

        visit_count = WatchHistory.objects.filter(ip_address=v.ip_address).count()
        online = _compute_online_from_last_watch(last_watch)

        rows.append({
            "id": v.id,
            "name": v.ip_address,
            "ip": v.ip_address,
            "country": v.country or "",
            "city": v.city or "",
            "online": online,
            "visit_count": visit_count,
            "last_visit": v.last_visit.strftime("%Y-%m-%d %H:%M:%S") if v.last_visit else "",
            "last_movie": last_watch.movie.name if last_watch and last_watch.movie else "-",
        })
    return JsonResponse({"visitors": rows})


def visitor_chart_data(request):
    today = timezone.now().date()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    data = []
    for d in days:
        count = Visitor.objects.filter(last_visit__date=d).count()
        data.append({"date": d.strftime("%Y-%m-%d"), "count": count})
    return JsonResponse({"data": data})


def visitor_country_data(request):
    by_country = Visitor.objects.values("country").annotate(count=Count("id")).order_by('-count')
    return JsonResponse({"data": list(by_country)})


def visitor_map_data(request):
    visitors = Visitor.objects.all()
    payload = []
    for v in visitors:
        last_watch = WatchHistory.objects.filter(ip_address=v.ip_address).order_by('-start_time').first()
        payload.append({
            "ip": v.ip_address,
            "country": v.country or "",
            "city": v.city or "",
            "lat": v.lat,
            "lng": v.lng,
            "online": _compute_online_from_last_watch(last_watch),
        })
    return JsonResponse({"data": payload})
