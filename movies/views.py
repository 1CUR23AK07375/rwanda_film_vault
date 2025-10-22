# movies/views.py
from django.utils.timezone import now
from datetime import timedelta
from django.utils import timezone
from django.utils.timesince import timesince
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count, F
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .models import Movie, Comment, WatchHistory, Visitor, DownloadHistory
from .utils.ip_tracker import get_client_ip, get_geoip_location

TRENDING_LIMIT = 8
NEW_RELEASES_LIMIT = 8
MAIN_PAGE_LIMIT = 20
ACTIVE_WINDOW_MINUTES = 10


def _safe_geoip(ip):
    """Safe GeoIP lookup wrapper."""
    try:
        return get_geoip_location(ip)
    except Exception:
        return "", "", 0.0, 0.0


# ============================================================
# Home Page
# ============================================================
def home(request):
    """
    Homepage view: shows trending, new releases, and all movies.
    Provides genre list for filter dropdown.
    """
    # --- Get query params ---
    search_query = request.GET.get('q', '').strip()
    selected_genre = request.GET.get('genre', '').strip()
    selected_sort = request.GET.get('sort', '').strip()

    # --- Base queryset ---
    movies_qs = Movie.objects.all()

    # --- Search filter ---
    if search_query:
        movies_qs = movies_qs.filter(name__icontains=search_query)

    # --- Genre filter ---
    if selected_genre:
        movies_qs = movies_qs.filter(genre__iexact=selected_genre)

    # --- Sorting ---
    if selected_sort == 'trending':
        # trending = most downloaded
        movies_qs = movies_qs.order_by('-download_count', '-uploaded_at')
    elif selected_sort == 'new':
        movies_qs = movies_qs.order_by('-uploaded_at')
    else:
        movies_qs = movies_qs.order_by('-uploaded_at')

    # --- Separate sections ---
    trending_movies = Movie.objects.order_by('-download_count', '-uploaded_at')[:6]
    new_releases = Movie.objects.order_by('-uploaded_at')[:6]
    all_movies = movies_qs

    # --- Unique genres for dropdown ---
    all_genres = Movie.objects.exclude(genre__isnull=True)\
                          .exclude(genre__exact='')\
                          .values_list('genre', flat=True)\
                          .distinct()\
                          .order_by('genre')
    
    all_genres = Movie.objects.exclude(genre__isnull=True).exclude(genre__exact='').values_list('genre', flat=True).distinct().order_by('genre')


    context = {
        'search_query': search_query,
        'selected_genre': selected_genre,
        'selected_sort': selected_sort,
        'trending_movies': trending_movies,
        'new_releases': new_releases,
        'movies': all_movies,
        'genres': all_genres,  # for your <select> in template
        'total_movies': Movie.objects.count(),
    }

    return render(request, 'movies/home.html', context)

# ============================================================
# Watch Movie + Comments
# ============================================================
def watch_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    last_comment = movie.comment_set.order_by("-id").first()
    last_comment_id = last_comment.id if last_comment else 0

    if request.method == "POST":
        text = (request.POST.get("text") or "").strip()
        guest_name = (request.POST.get("guest_name") or "").strip()
        if text:
            comment = Comment.objects.create(
                movie=movie,
                user=request.user if request.user.is_authenticated else None,
                guest_name=guest_name or None,
                text=text,
            )
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "count": movie.comment_set.count(),
                    "latest_comment": {
                        "id": comment.id,
                        "guest_name": comment.guest_name or "",
                        "user": comment.user.username if comment.user else None,
                        "text": comment.text,
                        "created_at": timesince(comment.created_at) + " ago",
                    },
                })
            return redirect("movies:watch_movie", movie_id=movie.id)

    comments = movie.comment_set.select_related("user").order_by("-id")
    total_views = movie.total_views if hasattr(movie, "total_views") else WatchHistory.objects.filter(movie=movie).count()
    active_window = timezone.now() - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    live_viewers = WatchHistory.objects.filter(movie=movie, end_time__isnull=True, start_time__gte=active_window).count()

    return render(request, "movies/watch_movie.html", {
        "movie": movie,
        "comments": comments,
        "last_comment_id": last_comment_id,
        "total_views": total_views,
        "live_viewers": live_viewers,
    })


# ============================================================
# Comments Feed (AJAX)
# ============================================================
def comments_feed(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    since_id = int(request.GET.get("since", 0) or 0)
    qs = movie.comment_set.select_related("user").order_by("id")
    if since_id > 0:
        qs = qs.filter(id__gt=since_id)

    comments = [{
        "id": c.id,
        "guest_name": c.guest_name or "",
        "user": c.user.username if c.user else None,
        "text": c.text,
        "created_at_display": timesince(c.created_at) + " ago",
        "created_at_iso": c.created_at.isoformat(),
    } for c in qs]

    total_views = movie.total_views if hasattr(movie, "total_views") else WatchHistory.objects.filter(movie=movie).count()
    active_window = timezone.now() - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    live_viewers = WatchHistory.objects.filter(movie=movie, end_time__isnull=True, start_time__gte=active_window).count()

    return JsonResponse({
        "comments": comments,
        "count": movie.comment_set.count(),
        "total_views": total_views,
        "live_viewers": live_viewers,
    })


# ============================================================
# Real-Time Viewers API
# ============================================================
def real_time_viewers(request, movie_id):
    active_window = timezone.now() - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    count = WatchHistory.objects.filter(movie_id=movie_id, end_time__isnull=True, start_time__gte=active_window).count()
    return JsonResponse({"count": count})


# ============================================================
# Download Movie
# ============================================================
def download_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if not movie.download_url:
        return HttpResponse("No download link available for this movie.", status=404)

    ip = get_client_ip(request)
    with transaction.atomic():
        DownloadHistory.objects.create(
            movie=movie,
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip,
        )
        Movie.objects.filter(id=movie.id).update(download_count=F("download_count") + 1)

    return redirect(movie.download_url)


# ============================================================
# Comment count API
# ============================================================
def comment_count_api(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    return JsonResponse({"count": movie.comment_set.count()})


# ============================================================
# Watch tracking (start / stop)
# ============================================================
@csrf_exempt
def start_watch(request, movie_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    movie = get_object_or_404(Movie, id=movie_id)
    ip = get_client_ip(request)

    # Close dangling sessions
    WatchHistory.objects.filter(movie=movie, ip_address=ip, end_time__isnull=True).update(end_time=timezone.now())

    watch = WatchHistory.objects.create(
        movie=movie,
        user=request.user if request.user.is_authenticated else None,
        ip_address=ip,
        start_time=timezone.now(),
    )

    Movie.objects.filter(id=movie.id).update(total_views=F("total_views") + 1)

    # Visitor update
    country, city, lat, lng = _safe_geoip(ip)
    visitor, _ = Visitor.objects.get_or_create(ip_address=ip, defaults={
        "country": country,
        "city": city,
        "lat": lat,
        "lng": lng,
        "last_visit": timezone.now(),
        "visit_count": 1
    })
    if visitor:
        visitor.country = country or visitor.country
        visitor.city = city or visitor.city
        visitor.lat = lat or visitor.lat
        visitor.lng = lng or visitor.lng
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
        h, m, s = (
            total_seconds // 3600,
            (total_seconds % 3600) // 60,
            total_seconds % 60,
        )
        formatted_duration = f"{h:02d}:{m:02d}:{s:02d}"

    return JsonResponse({"status": "stopped", "duration": formatted_duration})


# ============================================================
# Admin dashboard + Visitor APIs
# ============================================================
def admin_dashboard(request):
    return render(request, "movies/admin_dashboard.html", {})


def _is_online(last_watch):
    if not last_watch:
        return False
    return last_watch.end_time is None and last_watch.start_time and (timezone.now() - last_watch.start_time <= timedelta(minutes=ACTIVE_WINDOW_MINUTES))


def visitor_stats_api(request):
    visitors = Visitor.objects.all().order_by("-last_visit")
    rows = []
    for v in visitors:
        last_watch = WatchHistory.objects.filter(ip_address=v.ip_address).select_related("movie").order_by("-start_time").first()
        rows.append({
            "id": v.id,
            "name": v.ip_address,
            "ip": v.ip_address,
            "country": v.country or "",
            "city": v.city or "",
            "online": _is_online(last_watch),
            "visit_count": WatchHistory.objects.filter(ip_address=v.ip_address).count(),
            "last_visit": v.last_visit.strftime("%Y-%m-%d %H:%M:%S") if v.last_visit else "",
            "last_movie": last_watch.movie.name if last_watch and last_watch.movie else "-",
        })
    return JsonResponse({"visitors": rows})


def visitor_chart_data(request):
    today = timezone.now().date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    data = [{"date": d.strftime("%Y-%m-%d"), "count": Visitor.objects.filter(last_visit__date=d).count()} for d in days]
    return JsonResponse({"data": data})


def visitor_country_data(request):
    data = Visitor.objects.values("country").annotate(count=Count("id")).order_by("-count")
    return JsonResponse({"data": list(data)})


def visitor_map_data(request):
    visitors = Visitor.objects.all()
    payload = []
    for v in visitors:
        last_watch = WatchHistory.objects.filter(ip_address=v.ip_address).order_by("-start_time").first()
        country, city, lat, lng = _safe_geoip(v.ip_address)
        payload.append({
            "ip": v.ip_address,
            "country": v.country or country,
            "city": v.city or city,
            "lat": v.lat or lat,
            "lng": v.lng or lng,
            "online": _is_online(last_watch),
            "visit_count": WatchHistory.objects.filter(ip_address=v.ip_address).count(),
        })
    return JsonResponse({"data": payload})


def search_suggestions(request):
    q = request.GET.get('q', '')
    matches = Movie.objects.filter(name__icontains=q)[:5]
    results = [{'id': m.id, 'name': m.name} for m in matches]
    return JsonResponse(results, safe=False)


def latest_movies(request):
    recent_time = now() - timedelta(minutes=10)
    movies = Movie.objects.filter(uploaded_at__gte=recent_time).order_by('-uploaded_at')
    data = [
        {
            'id': m.id,
            'name': m.name,
            'image_url': m.image_url or '',
            'genre': m.genre or '',
            'download_url': m.download_url or ''
        }
        for m in movies
    ]
    return JsonResponse(data, safe=False)


def comment_count(request, movie_id):
    count = Comment.objects.filter(movie_id=movie_id).count()
    return JsonResponse({'movie_id': movie_id, 'comment_count': count})
