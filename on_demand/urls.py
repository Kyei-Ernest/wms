from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OnDemandRequestViewSet

# Create DRF router
router = DefaultRouter()
router.register(r'', OnDemandRequestViewSet, basename='on-demand-request')

urlpatterns = [
    path('', include(router.urls)),
]
