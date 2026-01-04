from django.db import models
try:
    # Django 3.1+
    from django.db.models import JSONField
except Exception:
    # fallback for older Django/Postgres installations
    from django.contrib.postgres.fields import JSONField


class QuestionBank(models.Model):
    q_id = models.AutoField(primary_key=True)
    taxo_subject = models.CharField(max_length=50, null=True, blank=True)
    taxo_section = models.CharField(max_length=100, null=True, blank=True)
    taxo_subsection = models.CharField(max_length=100, null=True, blank=True)
    taxo_lot = models.CharField(max_length=100, null=True, blank=True)
    q_code = models.CharField(max_length=50, unique=True)
    q_parent_code = models.CharField(max_length=50, null=True, blank=True)
    q_order = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    q_type = models.CharField(max_length=50, null=True, blank=True)
    q_bloom = models.CharField(max_length=50, null=True, blank=True)
    q_difficulty = models.CharField(max_length=20, null=True, blank=True)
    q_content = JSONField(null=True, blank=True)
    q_answers = JSONField(null=True, blank=True)
    q_hints = JSONField(null=True, blank=True)
    q_solution = JSONField(null=True, blank=True)
    q_properties = JSONField(null=True, blank=True)
    q_tags = JSONField(null=True, blank=True)
    q_status = models.CharField(max_length=20, null=True, blank=True)
    q_metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "question_bank"
        managed = False
        app_label = "question_bank"
        ordering = ("-created_at",)

    def __str__(self):
        return self.q_code
