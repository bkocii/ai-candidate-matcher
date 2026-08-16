"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from config.views import liveness, readiness

urlpatterns = [
    path("health/live/", liveness, name="health-live"),
    path("health/ready/", readiness, name="health-ready"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("audit.urls")),
    path("", include("candidates.urls")),
    path("", include("matching.urls")),
    path("", include("operations.urls")),
    path("", include("outreach.urls")),
    path("", include("vacancies.urls")),
    path("", include("organizations.urls")),
]
