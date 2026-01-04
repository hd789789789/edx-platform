from rest_framework import serializers
from .models import QuestionBank


class QuestionBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionBank
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


