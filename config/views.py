"""Content-free process health endpoints for production supervision."""

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe


def _health_response(*, status: str, status_code: int = 200) -> JsonResponse:
    response = JsonResponse({"status": status}, status=status_code)
    response["Cache-Control"] = "no-store"
    return response


@require_safe
def liveness(request):
    """Report that the web process can serve Django requests."""
    return _health_response(status="ok")


@require_safe
def readiness(request):
    """Report whether the web process can execute a database query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return _health_response(status="unavailable", status_code=503)
    return _health_response(status="ok")
