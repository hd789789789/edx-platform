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


# ============= Top Grades Serializers =============

class TopGradesStudentSerializer(ReadOnlySerializer):
    """
    Serializer for individual student in top grades leaderboard
    """
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    grade_percentage = serializers.FloatField()
    letter_grade = serializers.CharField(allow_blank=True)
    is_passed = serializers.BooleanField()
    passed_date = serializers.CharField(allow_null=True)
    grade_modified = serializers.CharField(allow_null=True)
    is_current_user = serializers.BooleanField()


class TopGradesSummarySerializer(ReadOnlySerializer):
    """
    Serializer for top grades summary statistics
    """
    total_students = serializers.IntegerField()
    avg_grade = serializers.FloatField()
    max_grade = serializers.FloatField()
    min_grade = serializers.FloatField()
    top_count = serializers.IntegerField()


class TopGradesSerializer(ReadOnlySerializer):
    """
    Serializer for Top Grades API response
    """
    success = serializers.BooleanField()
    course_id = serializers.CharField()
    leaderboard_type = serializers.CharField()
    timestamp = serializers.CharField()
    summary = TopGradesSummarySerializer()
    top_students = TopGradesStudentSerializer(many=True)
    current_user_entry = TopGradesStudentSerializer(
        allow_null=True, required=False)


# ============= Top Progress Serializers =============

class TopProgressStudentSerializer(ReadOnlySerializer):
    """
    Serializer for individual student in top progress leaderboard
    """
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    progress_percent = serializers.FloatField()
    is_current_user = serializers.BooleanField()


class TopProgressSummarySerializer(ReadOnlySerializer):
    """
    Serializer for top progress summary statistics
    """
    total_students_with_progress = serializers.IntegerField()
    avg_progress = serializers.FloatField()
    top_count = serializers.IntegerField()


class TopProgressSerializer(ReadOnlySerializer):
    """
    Serializer for Top Progress API response
    """
    success = serializers.BooleanField()
    course_id = serializers.CharField()
    leaderboard_type = serializers.CharField()
    period = serializers.CharField()
    timestamp = serializers.CharField()
    summary = TopProgressSummarySerializer()
    top_students = TopProgressStudentSerializer(many=True)
    current_user_entry = TopProgressStudentSerializer(
        allow_null=True, required=False)


# ============= Top Streak Serializers =============

class TopStreakStudentSerializer(ReadOnlySerializer):
    """
    Serializer cho từng học viên trong bảng xếp hạng streak
    """
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    current_streak = serializers.IntegerField()
    longest_ever_streak = serializers.IntegerField()
    is_current_user = serializers.BooleanField()


class TopStreakSummarySerializer(ReadOnlySerializer):
    """
    Thống kê tổng quan cho leaderboard streak
    """
    total_students_with_streak = serializers.IntegerField()
    avg_streak = serializers.FloatField()
    max_streak = serializers.IntegerField()
    top_count = serializers.IntegerField()


class TopStreakSerializer(ReadOnlySerializer):
    """
    Serializer cho API Top Streak
    """
    success = serializers.BooleanField()
    course_id = serializers.CharField()
    leaderboard_type = serializers.CharField()
    mode = serializers.CharField()  # 'current' hoặc 'best'
    timestamp = serializers.CharField()
    summary = TopStreakSummarySerializer()
    top_students = TopStreakStudentSerializer(many=True)
    current_user_entry = TopStreakStudentSerializer(
        allow_null=True, required=False)


# ============= Top XP Serializers =============

class TopXpStudentSerializer(ReadOnlySerializer):
    """
    Serializer for individual student in top XP leaderboard
    """
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    xp = serializers.IntegerField()
    level = serializers.IntegerField(allow_null=True, required=False)
    is_current_user = serializers.BooleanField()


class TopXpSummarySerializer(ReadOnlySerializer):
    """
    Serializer for top XP summary statistics
    """
    total_students = serializers.IntegerField()
    avg_xp = serializers.FloatField()
    max_xp = serializers.IntegerField()
    top_count = serializers.IntegerField()


class TopXpSerializer(ReadOnlySerializer):
    """
    Serializer for Top XP API response
    """
    success = serializers.BooleanField()
    course_id = serializers.CharField()
    leaderboard_type = serializers.CharField()
    timestamp = serializers.CharField()
    summary = TopXpSummarySerializer()
    top_students = TopXpStudentSerializer(many=True)
    current_user_entry = TopXpStudentSerializer(allow_null=True, required=False)


# ============= Top Coins Serializers =============

class TopCoinsStudentSerializer(ReadOnlySerializer):
    """
    Serializer for individual student in top coins/xu leaderboard
    """
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    coins = serializers.IntegerField()
    is_current_user = serializers.BooleanField()


class TopCoinsSummarySerializer(ReadOnlySerializer):
    """
    Serializer for top coins summary statistics
    """
    total_students = serializers.IntegerField()
    avg_coins = serializers.FloatField()
    max_coins = serializers.IntegerField()
    top_count = serializers.IntegerField()


class TopCoinsSerializer(ReadOnlySerializer):
    """
    Serializer for Top Coins API response
    """
    success = serializers.BooleanField()
    course_id = serializers.CharField()
    leaderboard_type = serializers.CharField()
    timestamp = serializers.CharField()
    summary = TopCoinsSummarySerializer()
    top_students = TopCoinsStudentSerializer(many=True)
    current_user_entry = TopCoinsStudentSerializer(allow_null=True, required=False)