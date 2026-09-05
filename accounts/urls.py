from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordResetCompleteView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy

from accounts.views import (
    RequiredAwarePasswordChangeView,
    RequiredAwarePasswordResetConfirmView,
)

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "password/reset/",
        PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password-reset-done"),
        ),
        name="password-reset",
    ),
    path(
        "password/reset/done/",
        PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password-reset-done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        RequiredAwarePasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password-reset-complete"),
        ),
        name="password-reset-confirm",
    ),
    path(
        "password/reset/complete/",
        PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password-reset-complete",
    ),
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
