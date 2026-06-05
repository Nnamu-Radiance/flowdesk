from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from apps.auth.permissions import is_admin_user


class AdminConfigView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "pages/admin_config.html"

    def test_func(self):
        return is_admin_user(self.request.user)