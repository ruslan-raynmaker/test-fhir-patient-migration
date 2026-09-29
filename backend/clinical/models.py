from django.db import models


class Patient(models.Model):
    fhir_id = models.CharField(max_length=64, unique=True)
    given_name = models.CharField(max_length=255, blank=True)
    family_name = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=16, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["family_name", "given_name", "id"]
        indexes = [models.Index(fields=["family_name", "given_name"])]

    def __str__(self):
        return f"Patient<{self.fhir_id}>"


class Observation(models.Model):
    fhir_id = models.CharField(max_length=64, unique=True)
    patient = models.ForeignKey(Patient, related_name="observations", on_delete=models.CASCADE)
    status = models.CharField(max_length=32, blank=True)
    category = models.CharField(max_length=64, blank=True)
    code = models.CharField(max_length=64, blank=True)
    code_system = models.CharField(max_length=255, blank=True)
    display = models.CharField(max_length=255, blank=True)
    effective_at = models.DateTimeField(null=True, blank=True)
    value_number = models.FloatField(null=True, blank=True)
    value_unit = models.CharField(max_length=64, blank=True)
    value_text = models.CharField(max_length=255, blank=True)
    components = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-effective_at", "id"]
        indexes = [models.Index(fields=["patient", "-effective_at"])]

    def __str__(self):
        return f"Observation<{self.fhir_id}>"


class ImportRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running"
        COMPLETED = "completed"
        PARTIAL = "partial"
        FAILED = "failed"

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    patients_imported = models.PositiveIntegerField(default=0)
    observations_imported = models.PositiveIntegerField(default=0)
    failures = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
