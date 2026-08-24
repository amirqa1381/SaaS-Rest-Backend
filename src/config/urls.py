from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include


def health_check(request):
    """Basic liveness endpoint — deeper DB/Redis/Celery checks added in Milestone 13."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/v1/auth/", include("apps.accounts.urls")),  # wired up as domain apps land
    # path("api/v1/", include("config.api_urls")),  # wired up as domain apps land
]
