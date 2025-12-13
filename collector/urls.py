from django.urls import path
from .views import (
    CollectorCreateView,
    CollectorListView,
    CollectorProfileView,
    CollectorsByCompanyView,
    CollectorsBySupervisorView,
    PrivateCollectorsListView,
    CollectorsByZoneView,
    CollectorApprovalView,
)

urlpatterns = [
    # ---------------------------
    # Registration
    # ---------------------------
    # POST /collectors/register/
    # - Private collectors can self-register (active immediately).
    # - Companies can register non-private collectors (status=pending_approval).
    # - Companies cannot register private collectors.
    path("register/", CollectorCreateView.as_view(), name="collector-register"),

    # ---------------------------
    # Listing
    # ---------------------------
    # GET /collectors/
    # - List all collectors (supervisors/companies can see all, clients usually won’t use this).
    path("", CollectorListView.as_view(), name="collector-list"),

    # GET /collectors/private/
    # - List all independent/private collectors.
    path("private/", PrivateCollectorsListView.as_view(), name="private-collectors-list"),

    # GET /collectors/company/{company_id}/
    # - List all collectors tied to a specific company (excluding private).
    path("company/<int:company_id>/", CollectorsByCompanyView.as_view(), name="collectors-by-company"),

    # GET /collectors/supervisor/{supervisor_id}/
    # - List all collectors under a specific supervisor.
    path("supervisor/<int:supervisor_id>/", CollectorsBySupervisorView.as_view(), name="collectors-by-supervisor"),

    # GET /collectors/zone/?zone=East+Legon&active=true
    # - List collectors assigned to a zone.
    # - Optional query param `active=true` filters only active collectors.
    path("zone/", CollectorsByZoneView.as_view(), name="collectors-by-zone"),

    # ---------------------------
    # Profile (self)
    # ---------------------------
    # GET /collectors/me/
    # - Authenticated collector retrieves their own profile.
    # PUT/PATCH /collectors/me/
    # - Update profile (full or partial).
    path("me/", CollectorProfileView.as_view(), name="collector-profile"),

    # ---------------------------
    # Company Approval Flow
    # ---------------------------
    # POST /collectors/{collector_id}/approval/
    # - Company approves or rejects a pending collector.
    # - Request body: {"action": "approve"} or {"action": "reject"}
    path("<int:collector_id>/approval/", CollectorApprovalView.as_view(), name="collector-approval"),
]
