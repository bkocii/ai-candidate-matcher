from urllib.parse import urlencode, urlparse

from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetConfirmView,
)
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def _safe_return_url(request):
    candidate = request.POST.get("next") or request.GET.get("next")
    if not candidate or not url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return None
    excluded_paths = {
        reverse("accounts:password-change"),
        reverse("accounts:password-change-done"),
        reverse("accounts:logout"),
    }
    if urlparse(candidate).path in excluded_paths:
        return None
    return candidate


class RequiredAwarePasswordChangeView(PasswordChangeView):
    """Clear the managed-account gate after a successful private password change."""

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            self.request.user.must_change_password = False
            self.request.user.save(update_fields=("must_change_password",))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["return_url"] = _safe_return_url(self.request)
        return context

    def get_success_url(self):
        success_url = super().get_success_url()
        return_url = _safe_return_url(self.request)
        if return_url:
            return f"{success_url}?{urlencode({'next': return_url})}"
        return success_url


class SafePasswordChangeDoneView(PasswordChangeDoneView):
    """Return only to a validated same-site location after a password change."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["return_url"] = _safe_return_url(self.request)
        return context


class RequiredAwarePasswordResetConfirmView(PasswordResetConfirmView):
    """Treat a successful one-time reset as the required private password setup."""

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.user.must_change_password:
            form.user.must_change_password = False
            form.user.save(update_fields=("must_change_password",))
        return response
