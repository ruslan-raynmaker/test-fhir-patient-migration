from rest_framework import serializers

from .models import Observation, Patient


class ObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Observation
        fields = [
            "id", "fhir_id", "status", "category", "code", "code_system", "display",
            "effective_at", "value_number", "value_unit", "value_text", "components",
        ]


class PatientListSerializer(serializers.ModelSerializer):
    observation_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "fhir_id", "given_name", "family_name", "gender", "birth_date", "observation_count"]


class PatientDetailSerializer(serializers.ModelSerializer):
    observations = ObservationSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "fhir_id", "given_name", "family_name", "gender", "birth_date",
            "source_updated_at", "observations",
        ]
