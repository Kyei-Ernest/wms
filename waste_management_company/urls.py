from django.urls import path
from .views import (
    CompanyRegisterView,
    CompanyProfileView,
    # CompanyDashboardView,   # Uncomment when dashboard is implemented
)

urlpatterns = [
    # -----------------------------------------------------
    # AUTH
    # -----------------------------------------------------
    path("register/", CompanyRegisterView.as_view(), name="company-register"),

    # -----------------------------------------------------
    # PROFILE
    # -----------------------------------------------------
    path("profile/", CompanyProfileView.as_view(), name="company-profile"),

    # -----------------------------------------------------
    # DASHBOARD (Placeholder)
    # -----------------------------------------------------
    # path("company/dashboard/", CompanyDashboardView.as_view(), name="company-dashboard"),
]
