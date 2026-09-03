from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
)
from django.urls import path, reverse_lazy

from accounts.views import RequiredAwarePasswordChangeView

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "password/change/",
        RequiredAwarePasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("accounts:password-change-done"),
        ),
        name="password-change",
    ),
    path(
        "password/change/done/",
        PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password-change-done",
    ),
]
