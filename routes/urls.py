from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RouteViewSet, RouteStopViewSet

router = DefaultRouter()
router.register(r'', RouteViewSet, basename='route')
router.register(r'route-stops', RouteStopViewSet, basename='route-stop')

urlpatterns = [
    path('', include(router.urls)),
]
