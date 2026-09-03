"""Response protections shared by authenticated application pages."""

from django.shortcuts import redirect
from django.urls import reverse


class RequiredPasswordChangeMiddleware:
    """Keep managed users out of workspaces until temporary credentials change."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.must_change_password:
            allowed_paths = {
                reverse("accounts:password-change"),
                reverse("accounts:password-change-done"),
                reverse("accounts:logout"),
            }
            if request.path not in allowed_paths:
                return redirect("accounts:password-change")
        return self.get_response(request)


class AuthenticatedHTMLNoStoreMiddleware:
    """Prevent protected HTML from being restored after the session ends."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        was_authenticated = request.user.is_authenticated
        response = self.get_response(request)

        content_type = response.get("Content-Type", "").partition(";")[0].lower()
        if was_authenticated and content_type == "text/html":
            response["Cache-Control"] = "no-store, private, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
