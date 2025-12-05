from django.urls import path
from .views import (
    ClientCreateView, ClientListView,
    ClientProfileView
)

urlpatterns = [
    path('list/', ClientListView.as_view(), name='client-list'),
    path('register/', ClientCreateView.as_view(), name='client-create'),
    
    path('profile/', ClientProfileView.as_view(), name='client-profile'),
]
