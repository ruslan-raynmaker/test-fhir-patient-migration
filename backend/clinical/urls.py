from django.urls import path

from . import views

urlpatterns = [
    path("patients/", views.PatientListView.as_view(), name="patient-list"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient-detail"),
]
