from django.db.models import Sum, Count, F, Q
from django.core.cache import cache
from .models import Order, Booking, Seat
from django.utils import timezone
from datetime import timedelta

def get_dashboard_stats():
    # Attempt to fetch from Redis Cache (60 second TTL to avoid slamming DB)
    cached_stats = cache.get('admin_dashboard_stats')
    if cached_stats:
        return cached_stats

    # 1. Total Revenue (Daily)
    today = timezone.now().date()
    daily_revenue = Order.objects.filter(
        payment_status='Paid', 
        created_at__date=today
    ).aggregate(total=Sum('total_price'))['total'] or 0

    # 2. Most Popular Movies (Aggregation)
    popular_movies = Booking.objects.values('movie__name') \
        .annotate(booking_count=Count('id')) \
        .order_by('-booking_count')[:5]

    # 3. Occupancy Rate (Database-level calculation)
    total_seats = Seat.objects.count()
    booked_seats = Seat.objects.filter(is_booked=True).count()
    occupancy_rate = (booked_seats / total_seats * 100) if total_seats > 0 else 0

    # 4. Peak Hours (Extracting hour from datetime)
    peak_hours = Order.objects.filter(payment_status='Paid') \
        .values('created_at__hour') \
        .annotate(count=Count('id')) \
        .order_by('-count')[:1]

    stats = {
        'daily_revenue': daily_revenue,
        'popular_movies': list(popular_movies),
        'occupancy_rate': round(occupancy_rate, 2),
        'peak_hour': peak_hours[0]['created_at__hour'] if peak_hours else "N/A"
    }

    # Store in Redis
    cache.set('admin_dashboard_stats', stats, 60)
    return stats