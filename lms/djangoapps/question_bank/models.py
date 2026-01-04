from django.db import models
try:
    # Django 3.1+
    from django.db.models import JSONField
except Exception:
    # fallback for older Django/Postgres installations
    from django.contrib.postgres.fields import JSONField


class QuestionBank(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True)
    parent_id = models.IntegerField(null=True, blank=True)
    has_sub_questions = models.NullBooleanField(null=True, blank=True) if hasattr(models, "NullBooleanField") else models.BooleanField(null=True, blank=True)
    sub_question_order = models.IntegerField(null=True, blank=True)
    taxonomy = JSONField(null=True, blank=True)
    question_type = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)
    difficulty = models.CharField(max_length=20, null=True, blank=True)
    content = JSONField(null=True, blank=True)
    sub_questions = JSONField(null=True, blank=True)
    answers = JSONField(null=True, blank=True)
    hints = JSONField(null=True, blank=True)
    solution = JSONField(null=True, blank=True)
    properties = JSONField(null=True, blank=True)
    tags = JSONField(null=True, blank=True)
    keywords = models.TextField(null=True, blank=True)
    statistics = JSONField(null=True, blank=True)
    metadata = JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    is_public = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "question_bank"
        managed = False
        ordering = ("-created_at",)

    def __str__(self):
        return self.code


