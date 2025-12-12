from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduledRequestViewSet

# Create a router and register our viewset
router = DefaultRouter()
router.register(r'', ScheduledRequestViewSet, basename='scheduled-request')

urlpatterns = [
    path('', include(router.urls)),
]
