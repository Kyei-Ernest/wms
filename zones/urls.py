from django.urls import path
from .views import (
    ZoneCreateView, ZoneUpdateView, ZoneListView, ZoneDetailView, PointInZoneView
)

urlpatterns = [
    path("", ZoneListView.as_view(), name="zone-list"),
    path("create/", ZoneCreateView.as_view(), name="zone-create"),
    path("<int:zone_id>/", ZoneDetailView.as_view(), name="zone-detail"),
    path("<int:zone_id>/update/", ZoneUpdateView.as_view(), name="zone-update"),
    path("check-point/", PointInZoneView.as_view(), name="point-in-zone"),
]
