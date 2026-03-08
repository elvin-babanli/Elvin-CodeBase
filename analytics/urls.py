from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.dashboard_overview, name="dashboard"),
    path("live/", views.dashboard_live, name="live"),
    path("users/", views.dashboard_users, name="users"),
    path("guests/", views.dashboard_guests, name="guests"),
    path("traffic/", views.dashboard_traffic, name="traffic"),
    path("events/", views.dashboard_events, name="events"),
    path("devices/", views.dashboard_devices, name="devices"),
    path("countries/", views.dashboard_countries, name="countries"),
    path("ai-analysis/", views.dashboard_ai_analysis, name="ai_analysis"),
    path("reports/", views.dashboard_reports, name="reports"),
    path("user-management/", views.dashboard_user_management, name="user_management"),
    path("api/live/", views.api_live, name="api_live"),
    path("api/traffic/", views.api_traffic, name="api_traffic"),
    path("api/click/", views.api_click, name="api_click"),
    path("api/footprint/", views.api_footprint, name="api_footprint"),
    path("api/past-analyses/", views.api_past_analyses, name="api_past_analyses"),
    path("api/analyze/", views.api_analyze, name="api_analyze"),
    path("api/user/delete/<int:pk>/", views.api_user_delete, name="api_user_delete"),
    path("api/auth-event/delete/<int:pk>/", views.api_auth_event_delete, name="api_auth_event_delete"),
    path("api/click-event/delete/<int:pk>/", views.api_click_event_delete, name="api_click_event_delete"),
    path("api/export/csv/", views.api_export_csv, name="api_export_csv"),
    path("api/export/json/", views.api_export_json, name="api_export_json"),
]
