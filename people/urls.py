from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("<str:resource>/", views.people_list, name="list"),
    path("<str:resource>/new/", views.people_create, name="create"),
    path("<str:resource>/<int:pk>/", views.people_detail, name="detail"),
    path("<str:resource>/<int:pk>/edit/", views.people_update, name="update"),
    path("<str:resource>/<int:pk>/delete/", views.people_delete, name="delete"),
]
