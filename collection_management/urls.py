from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollectionRecordViewSet

router = DefaultRouter()
router.register(r'', CollectionRecordViewSet, basename='collection')

urlpatterns = [
    path('', include(router.urls)),
]

