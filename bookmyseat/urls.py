from django.contrib import admin
from django.urls import path, include
from movies.admin import analytics_site
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('users/', include('users.urls')),
    path('',include('users.urls')),
    path('movies/', include('movies.urls')),
    path('admin/', analytics_site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
