"""
Leaderboard Tab Serializers
"""
from rest_framework import serializers
from lms.djangoapps.course_home_api.serializers import ReadOnlySerializer


class LeaderboardEntrySerializer(ReadOnlySerializer):
    """
    Serializer for individual leaderboard entry
    """
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField()
    grade_percent = serializers.FloatField()
    letter_grade = serializers.CharField()
    is_passing = serializers.BooleanField()
    is_current_user = serializers.BooleanField()


class CurrentUserRankSerializer(ReadOnlySerializer):
    """
    Serializer for current user's rank information
    """
    rank = serializers.IntegerField()
    total_students = serializers.IntegerField()
    percentile = serializers.FloatField()


class LeaderboardTabSerializer(ReadOnlySerializer):
    """
    Serializer for Leaderboard Tab data
    """
    course_id = serializers.CharField()
    course_name = serializers.CharField()
    leaderboard = LeaderboardEntrySerializer(many=True)
    current_user_rank = CurrentUserRankSerializer(allow_null=True)
    total_students = serializers.IntegerField()
    top_performers = LeaderboardEntrySerializer(many=True)