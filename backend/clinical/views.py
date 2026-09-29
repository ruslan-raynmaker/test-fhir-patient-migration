from django.db.models import Count
from rest_framework import generics

from .models import Patient
from .serializers import PatientDetailSerializer, PatientListSerializer


class PatientListView(generics.ListAPIView):
    serializer_class = PatientListSerializer
    queryset = Patient.objects.annotate(observation_count=Count("observations")).order_by(
        "family_name", "given_name", "id"
    )


class PatientDetailView(generics.RetrieveAPIView):
    serializer_class = PatientDetailSerializer
    queryset = Patient.objects.prefetch_related("observations")
