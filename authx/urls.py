from django.urls import path
from authx.views import LoginView, RefreshView, MeView, LogoutView

urlpatterns = [
    path("login/", LoginView.as_view(), name="authx-login"),
    path("refresh/", RefreshView.as_view(), name="authx-refresh"),
    path("me/", MeView.as_view(), name="authx-me"),
    path("logout/", LogoutView.as_view(), name="authx-logout"),
]
