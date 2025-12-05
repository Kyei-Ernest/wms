from rest_framework.routers import DefaultRouter
from .views import RouteViewSet, RouteStopViewSet

router = DefaultRouter()
router.register('', RouteViewSet, basename='routes')
router.register('route-stops', RouteStopViewSet, basename='route-stops')

urlpatterns = router.urls
