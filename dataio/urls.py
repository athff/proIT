from django.urls import path

from . import views

urlpatterns = [
    path("", views.workspace, name="dataio-workspace"),
    path("export/<str:model_key>/", views.export_csv, name="csv-export"),
    path("template/<str:model_key>/", views.template_csv, name="csv-template"),
    path("import/<str:model_key>/", views.import_csv_view, name="csv-import"),
]
