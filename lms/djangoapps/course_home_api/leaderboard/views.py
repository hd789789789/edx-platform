"""
Leaderboard Tab Views
"""

from django.contrib.auth import get_user_model
from django.http.response import Http404
from django.db.models import Q
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys.edx.keys import CourseKey
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.course_home_api.leaderboard.serializers import LeaderboardTabSerializer
from lms.djangoapps.course_home_api.utils import get_course_or_403
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.grades.models import PersistentCourseGrade
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser

User = get_user_model()


class LeaderboardTabView(RetrieveAPIView):
    """
    **Use Cases**

        Request leaderboard data for a specific course

    **Example Requests**

        GET api/course_home/v1/leaderboard/{course_key}

    **Response Values**

        Body consists of the following fields:

        course_id: (str) The course key string
        leaderboard: List of student ranking objects, each containing:
            rank: (int) Student's rank position (1-based)
            username: (str) Student's username (or anonymized if configured)
            display_name: (str) Student's display name
            grade_percent: (float) Student's course grade percentage (0-100)
            letter_grade: (str) Student's letter grade (A, B, C, D, Pass, etc.)
            is_passing: (bool) Whether student has passing grade
            is_current_user: (bool) Whether this entry is the current user
        current_user_rank: Object containing current user's rank info:
            rank: (int) Current user's rank
            total_students: (int) Total number of students in leaderboard
            percentile: (float) Percentile ranking (0-100)
        total_students: (int) Total number of students enrolled and graded
        top_performers: List of top 3 students (subset of leaderboard)

    **Returns**

        * 200 on success with above fields.
        * 401 if the user is not authenticated.
        * 403 if the user does not have access to the course.
        * 404 if the course is not available or leaderboard is disabled.
    """

    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)
    serializer_class = LeaderboardTabSerializer

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)

        # Enable NR tracing for this view based on course
        monitoring_utils.set_custom_attribute('course_id', course_key_string)
        monitoring_utils.set_custom_attribute('user_id', request.user.id)

        # Check if user has access to course
        course = get_course_or_403(request.user, 'load', course_key, check_if_enrolled=False)
        course_overview = CourseOverview.get_from_id(course_key)

        # Check if user is enrolled in the course
        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        is_staff = bool(has_access(request.user, 'staff', course_key))

        if not ((enrollment and enrollment.is_active) or is_staff):
            return Response('User not enrolled.', status=401)

        # Get all active enrollments for this course
        active_enrollments = CourseEnrollment.objects.filter(
            course_id=course_key,
            is_active=True
        ).select_related('user')

        # Get persistent course grades for all enrolled students
        # Only include students with grades > 0 to filter out inactive students
        course_grades = PersistentCourseGrade.objects.filter(
            course_id=course_key,
            user_id__in=active_enrollments.values_list('user_id', flat=True),
            percent_grade__gt=0  # Filter out students with no activity
        ).select_related('user').order_by('-percent_grade', 'user__username')

        # Build leaderboard data
        leaderboard_data = []
        current_user_entry = None
        rank = 1
        previous_grade = None

        for idx, grade in enumerate(course_grades):
            # Handle tie scores - same grade gets same rank
            if previous_grade is not None and grade.percent_grade < previous_grade:
                rank = idx + 1

            entry = {
                'rank': rank,
                'user_id': grade.user_id,
                'username': grade.user.username,
                'display_name': grade.user.profile.name if hasattr(grade.user, 'profile') else grade.user.username,
                'grade_percent': grade.percent_grade * 100,  # Convert to percentage
                'letter_grade': grade.letter_grade or '',
                'is_passing': grade.passed_timestamp is not None,
                'is_current_user': grade.user_id == request.user.id,
            }

            leaderboard_data.append(entry)

            if grade.user_id == request.user.id:
                current_user_entry = entry

            previous_grade = grade.percent_grade

        # Calculate current user rank info
        total_students = len(leaderboard_data)
        current_user_rank_info = None

        if current_user_entry:
            percentile = ((total_students - current_user_entry['rank']) / total_students * 100) if total_students > 0 else 0
            current_user_rank_info = {
                'rank': current_user_entry['rank'],
                'total_students': total_students,
                'percentile': round(percentile, 2),
            }

        # Get top 3 performers
        top_performers = leaderboard_data[:3] if len(leaderboard_data) >= 3 else leaderboard_data

        # Prepare response data
        data = {
            'course_id': course_key_string,
            'leaderboard': leaderboard_data,
            'current_user_rank': current_user_rank_info,
            'total_students': total_students,
            'top_performers': top_performers,
            'course_name': course_overview.display_name,
        }

        serializer = self.get_serializer_class()(data)
        return Response(serializer.data)
