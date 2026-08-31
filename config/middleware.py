"""Response protections shared by authenticated application pages."""


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
