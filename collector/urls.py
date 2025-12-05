from django.urls import path
from .views import (
    CollectorCreateView,
    CollectorListView,
    CollectorProfileView,
    CollectorsByCompanyView,
    CollectorsBySupervisorView,
    PrivateCollectorsListView,
)

urlpatterns = [
    path("create/", CollectorCreateView.as_view(), name="collector-create"),
    path("list/", CollectorListView.as_view(), name="collector-list"),
    path("profile/", CollectorProfileView.as_view(), name="collector-profile"),
    path("by-company/<str:company_username>/", CollectorsByCompanyView.as_view(), name="collectors-by-company"),
    path("by-supervisor/<str:supervisor_username>/", CollectorsBySupervisorView.as_view(), name="collectors-by-supervisor"),
    path("private/", PrivateCollectorsListView.as_view(), name="private-collectors"),
]
