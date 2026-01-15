from django.urls import path
from authx.views import LoginView, RefreshView, MeView, LogoutView, ActiveSessionListView, RevokeSessionView, RevokeOtherSessionsView

urlpatterns = [
    path("login/", LoginView.as_view(), name="authx-login"),
    path("refresh/", RefreshView.as_view(), name="authx-refresh"),
    path("me/", MeView.as_view(), name="authx-me"),
    path("logout/", LogoutView.as_view(), name="authx-logout"),
    # ---- sessions / devices ----
    path("sessions/", ActiveSessionListView.as_view(), name="authx-sessions"),
    path("sessions/<uuid:session_id>/revoke/", RevokeSessionView.as_view(), name="authx-session-revoke"),
    path("sessions/revoke-others/", RevokeOtherSessionsView.as_view(), name="authx-session-revoke-others"),

]
