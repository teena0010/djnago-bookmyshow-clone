from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from .models import Movie, Genre, Language, Theater, Seat, Booking, Order
from .admin_analytics import get_dashboard_stats

# 1. Define the Custom Admin Site
class AnalyticsAdminSite(admin.AdminSite):
    site_header = "Booking Analytics Dashboard"
    
    def index(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        extra_context['stats'] = get_dashboard_stats()
        return super().index(request, extra_context=extra_context)

# 2. Instantiate
analytics_site = AnalyticsAdminSite(name='analytics_admin')

# 3. Register Auth Models to Custom Site
analytics_site.register(User, UserAdmin)
analytics_site.register(Group, GroupAdmin)

# 4. Register All Your Models to Custom Site
@admin.register(Movie, site=analytics_site)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['name', 'rating', 'cast', 'description']

@admin.register(Theater, site=analytics_site)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ['name', 'movie', 'time']

@admin.register(Seat, site=analytics_site)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['theater', 'seat_number', 'is_booked']

@admin.register(Booking, site=analytics_site)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'seat', 'movie', 'theater', 'booked_at']

@admin.register(Genre, site=analytics_site)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Language, site=analytics_site)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Order, site=analytics_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'payment_status', 'total_price', 'created_at']