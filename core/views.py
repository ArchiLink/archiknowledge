from django.db import connection
from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Liveness check for Docker and the proxy: 200 when Django and the database respond."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")
