from django.urls import path
from .views import (
    SupervisorCreateView,
    SupervisorListView,
    SupervisorProfileView,
)

urlpatterns = [
    # Create supervisor (admin/company only)
    path("create/", SupervisorCreateView.as_view(), name="supervisor-create"),

    # List all supervisors
    path("list/", SupervisorListView.as_view(), name="supervisor-list"),

    # Supervisor's own profile
    path("profile/", SupervisorProfileView.as_view(), name="supervisor-profile"),
]
