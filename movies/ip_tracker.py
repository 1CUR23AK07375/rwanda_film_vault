# utils/ip_tracker.py
import geoip2.database
from django.conf import settings
import os
import ipaddress


def get_client_ip(request):
    """
    Extracts the real client IP, considering reverse proxies.
    Falls back to REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
    return ip


def is_private_ip(ip):
    """
    Returns True if the IP is private or local.
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved
    except ValueError:
        return True  # Treat invalid IP as private


def get_geoip_location(ip):
    """
    Returns (country, city, latitude, longitude).
    Private or invalid IPs return empty/defaults.
    Requires GeoLite2-City.mmdb in BASE_DIR or settings.GEOIP_PATH.
    """
    if is_private_ip(ip):
        return "", "", 0.0, 0.0

    try:
        db_path = getattr(settings, "GEOIP_PATH", os.path.join(settings.BASE_DIR, "GeoLite2-City.mmdb"))
        if not os.path.exists(db_path):
            return "", "", 0.0, 0.0

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
