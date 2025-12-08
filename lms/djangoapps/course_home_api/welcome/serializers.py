"""
Welcome Tab Serializers
"""

from rest_framework import serializers


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user statistics"""
    streak_days = serializers.IntegerField()
    completion_percent = serializers.FloatField()
    today_lessons = serializers.IntegerField()
    class_rank = serializers.IntegerField()
    last_day_of_streak = serializers.CharField(required=False, allow_null=True)


class ImportantDateSerializer(serializers.Serializer):
    """Serializer for important dates"""
    date = serializers.CharField()
    title = serializers.CharField()
    status = serializers.CharField()
    days_left = serializers.IntegerField(required=False, allow_null=True)


class DailyQuestSerializer(serializers.Serializer):
    """Serializer for daily quests (placeholder)"""
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    reward = serializers.CharField()
    progress = serializers.IntegerField()
    total = serializers.IntegerField()
    completed = serializers.BooleanField()
    icon = serializers.CharField()
    gradient = serializers.CharField()


class WelcomeTabSerializer(serializers.Serializer):
    """Serializer for Welcome Tab data"""
    success = serializers.BooleanField()
    user_stats = UserStatsSerializer()
    important_dates = ImportantDateSerializer(many=True)
    daily_quests = DailyQuestSerializer(many=True, required=False)

