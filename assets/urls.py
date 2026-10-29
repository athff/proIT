from django.urls import path

from . import views
from . import ticket_views

app_name = "assets"

urlpatterns = [
    path("", views.asset_list, name="list"),
    path("assign/", views.asset_assign, name="assign"),
    path("support/new/", ticket_views.ticket_create, name="ticket-create"),
    path("support/mine/", ticket_views.ticket_list, name="ticket-list"),
    path("support/admin/", ticket_views.ticket_admin_list, name="ticket-admin-list"),
    path("support/<str:reference>/", ticket_views.ticket_detail, name="ticket-detail"),
    path("support/<str:reference>/manage/", ticket_views.ticket_admin_detail, name="ticket-admin-detail"),
    path("new/", views.asset_create, name="create"),
    path("<int:pk>/", views.asset_detail, name="detail"),
    path("<int:pk>/qr-label/", views.asset_qr_label, name="qr-label"),
    path("<int:pk>/return/", views.asset_return, name="return"),
    path("<int:pk>/edit/", views.asset_update, name="update"),
    path("<int:pk>/delete/", views.asset_delete, name="delete"),
]
