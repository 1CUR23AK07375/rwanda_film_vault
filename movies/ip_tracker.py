# utils/ip_tracker.py
import geoip2.database
from django.conf import settings
import os


def get_client_ip(request):
    """
    Extracts the real client IP, considering reverse proxies.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_geoip_location(ip):
    """
    Returns (country, city, latitude, longitude).
    Requires GeoLite2-City.mmdb file in your BASE_DIR or GEOIP_PATH.
    """
    try:
        # Default: look for GeoLite2-City.mmdb in BASE_DIR
        db_path = getattr(settings, "GEOIP_PATH", os.path.join(settings.BASE_DIR, "GeoLite2-City.mmdb"))
        reader = geoip2.database.Reader(db_path)

        response = reader.city(ip)
        country = response.country.name or ""
        city = response.city.name or ""
        lat = response.location.latitude or 0.0
        lng = response.location.longitude or 0.0
        reader.close()

        return country, city, lat, lng
    except Exception:
        return "", "", 0.0, 0.0
