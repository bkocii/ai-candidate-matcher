from django.contrib.auth.views import PasswordChangeView, PasswordResetConfirmView


class RequiredAwarePasswordChangeView(PasswordChangeView):
    """Clear the managed-account gate after a successful private password change."""

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            self.request.user.must_change_password = False
            self.request.user.save(update_fields=("must_change_password",))
        return response


class RequiredAwarePasswordResetConfirmView(PasswordResetConfirmView):
    """Treat a successful one-time reset as the required private password setup."""

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.user.must_change_password:
            form.user.must_change_password = False
            form.user.save(update_fields=("must_change_password",))
        return response
