from django.urls import path
from .views import (
     LoginView, LogoutView, TokenRefreshView
)

urlpatterns = [
    
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('login/', LoginView.as_view(), name="login"),
    path('logout/', LogoutView.as_view(), name='logout'),

]