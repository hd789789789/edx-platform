"""
Badge Tab Serializers
"""
from rest_framework import serializers
from lms.djangoapps.course_home_api.serializers import ReadOnlySerializer


class UnitBadgeSerializer(ReadOnlySerializer):
    """
    Serializer for Unit level badge
    """
    unit_id = serializers.CharField()
    unit_name = serializers.CharField()
    is_completed = serializers.BooleanField()
    completed_at = serializers.CharField(allow_null=True)


class SectionBadgeSerializer(ReadOnlySerializer):
    """
    Serializer for Section/Bài level badge
    """
    section_id = serializers.CharField()
    section_name = serializers.CharField()
    is_completed = serializers.BooleanField()
    completed_at = serializers.CharField(allow_null=True)
    total_units = serializers.IntegerField()
    completed_units = serializers.IntegerField()
    units = UnitBadgeSerializer(many=True)


class ChapterBadgeSerializer(ReadOnlySerializer):
    """
    Serializer for Chapter/Chương level badge
    """
    chapter_id = serializers.CharField()
    chapter_name = serializers.CharField()
    is_completed = serializers.BooleanField()
    completed_at = serializers.CharField(allow_null=True)
    total_sections = serializers.IntegerField()
    completed_sections = serializers.IntegerField()
    sections = SectionBadgeSerializer(many=True)


class BadgeSummarySerializer(ReadOnlySerializer):
    """
    Serializer for badge summary statistics
    """
    total_chapters = serializers.IntegerField()
    completed_chapters = serializers.IntegerField()
    total_sections = serializers.IntegerField()
    completed_sections = serializers.IntegerField()
    total_units = serializers.IntegerField()
    completed_units = serializers.IntegerField()
    completion_percentage = serializers.FloatField()


class BadgeResponseSerializer(ReadOnlySerializer):
    """
    Serializer for Badge API response
    """
    success = serializers.BooleanField()
    course_id = serializers.CharField()
    course_name = serializers.CharField()
    timestamp = serializers.CharField()
    summary = BadgeSummarySerializer()
    chapters = ChapterBadgeSerializer(many=True)

