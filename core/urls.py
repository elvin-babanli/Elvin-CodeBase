"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from main.views import *
from main import views
from main.views_extra import robots_txt, favicon_redirect

from main.weather_app import weather_project_view, weather_api
from main.stock_predictor import stock_predictor_view
from main.cheap_flight_finder import (
    cheap_flight_finder_view,
    cheap_flight_search_api,
    cheap_flight_locations_api,
    store_flight_context_api,
    restore_flight_context_api,
    send_sms_api,
    send_email_api,
    city_guide_api,
    place_photo_api,
    place_details_api,
)
from main.todo import todo_page, todo_task_detail_api, todo_toggle_api

from django.contrib.sitemaps.views import sitemap
from main.sitemap import StaticViewSitemap

sitemaps = {"static": StaticViewSitemap}

urlpatterns = [
    path("robots.txt", robots_txt),
    path("favicon.ico", favicon_redirect),
    path("admin/", admin.site.urls),
    path("auth/", include("accounts.urls")),
    path("admin-dashboard/", include("analytics.urls")),
    path("accounts/", include("allauth.urls")),
    path("", include("main.urls")),

    path("django/", get_django, name="django"),
    path("flask/", get_flask, name="flask"),
    path("pandas/", get_pandas, name="pandas"),
    path("git/", get_git, name="git"),
    path("crud/", get_crud, name="crud"),

    path("weather-app/", weather_project_view, name="weather_app"),
    path("weather-app/api/", weather_api, name="weather_api"),  # optional

    path("python-basics/", get_python_basics, name="python-basics"),
    path("about/", views.about, name="about"),
    path("4o4-page/", get4o4, name="4o4-page"),
    path("valentine-page/", valentine_page, name="valentine-page"), # Just for Test

    path("todo/", todo_page, name="todo"),
    path("todo/api/task/<int:task_id>/", todo_task_detail_api, name="todo_task_api"),
    path("todo/api/task/<int:task_id>/toggle/", todo_toggle_api, name="todo_toggle_api"),

    path("stock-predictor/", stock_predictor_view, name="stock-predictor"),
    path("cheap-flight-finder/", cheap_flight_finder_view, name="cheap_flight_finder"),
    path("cheap-flight-finder/api/search/", cheap_flight_search_api, name="cheap_flight_search_api"),
    path("cheap-flight-finder/api/locations/", cheap_flight_locations_api, name="cheap_flight_locations_api"),
    path("cheap-flight-finder/api/store-context/", store_flight_context_api, name="cff_store_context"),
    path("cheap-flight-finder/api/restore-context/", restore_flight_context_api, name="cff_restore_context"),
    path("cheap-flight-finder/api/send-sms/", send_sms_api, name="cff_send_sms"),
    path("cheap-flight-finder/api/send-email/", send_email_api, name="cff_send_email"),
    path("cheap-flight-finder/api/city-guide/", city_guide_api, name="cff_city_guide"),
    path("cheap-flight-finder/api/place-photo/", place_photo_api, name="cff_place_photo"),
    path("cheap-flight-finder/api/place-details/", place_details_api, name="cff_place_details"),

    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),

    path("numpy/", get_numpy, name="numpy"),
    path("matplotlib/", get_matplotlib, name="matplotlib"),
]

handler500 = "main.views_extra.server_error"
