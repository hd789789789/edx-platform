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
from lms.djangoapps.courseware.courses import get_course_blocks_completion_summary
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
            grade_percent: (float) Student's course completion percentage (0-100)
            letter_grade: (str) Student's letter grade (A, B, C, D, Pass, etc.) from grading
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
        )

        # Get all enrolled users
        enrolled_user_ids = list(active_enrollments.values_list('user_id', flat=True))
        all_users = User.objects.filter(id__in=enrolled_user_ids).select_related('profile')

        # Get persistent course grades for letter grade and passing status
        course_grades = PersistentCourseGrade.objects.filter(
            course_id=course_key,
            user_id__in=enrolled_user_ids
        )
        grades_dict = {grade.user_id: grade for grade in course_grades}

        # Calculate completion percentage for all users
        completion_data = []
        for user in all_users:
            completion_summary = get_course_blocks_completion_summary(course_key, user)
            complete_count = completion_summary.get('complete_count', 0)
            incomplete_count = completion_summary.get('incomplete_count', 0)
            locked_count = completion_summary.get('locked_count', 0)
            total_units = complete_count + incomplete_count + locked_count

            completion_percent = (complete_count / total_units * 100) if total_units > 0 else 0.0

            # Get grade info for letter grade and passing status
            grade = grades_dict.get(user.id)

            try:
                display_name = user.profile.name if user.profile.name else user.username
            except:
                display_name = user.username

            completion_data.append({
                'user': user,
                'user_id': user.id,
                'username': user.username,
                'display_name': display_name,
                'completion_percent': completion_percent,
                'letter_grade': grade.letter_grade if grade else '',
                'is_passing': grade.passed_timestamp is not None if grade else False,
                'is_current_user': user.id == request.user.id,
            })

        # Sort by completion percentage (highest first), then by username for ties
        completion_data.sort(key=lambda x: (-x['completion_percent'], x['username']))

        # Build leaderboard with ranking
        leaderboard_data = []
        current_user_entry = None
        rank = 1
        previous_completion = None

        for idx, entry in enumerate(completion_data):
            # Handle tie scores - same completion gets same rank
            if previous_completion is not None and entry['completion_percent'] < previous_completion:
                rank = idx + 1

            leaderboard_entry = {
                'rank': rank,
                'user_id': entry['user_id'],
                'username': entry['username'],
                'display_name': entry['display_name'],
                'grade_percent': entry['completion_percent'],  # Using completion_percent in grade_percent field
                'letter_grade': entry['letter_grade'],
                'is_passing': entry['is_passing'],
                'is_current_user': entry['is_current_user'],
            }

            leaderboard_data.append(leaderboard_entry)

            if entry['is_current_user']:
                current_user_entry = leaderboard_entry

            previous_completion = entry['completion_percent']

        # Calculate current user rank info
        total_students = len(leaderboard_data)
        current_user_rank_info = None

        # Debug logging
        import logging
        log = logging.getLogger(__name__)
        log.info(f"[Leaderboard] Request user ID: {request.user.id}")
        log.info(f"[Leaderboard] Total enrolled users: {len(enrolled_user_ids)}")
        log.info(f"[Leaderboard] Users with grades: {len(grades_dict)}")
        log.info(f"[Leaderboard] Total in leaderboard: {total_students}")
        log.info(f"[Leaderboard] Current user found: {current_user_entry is not None}")
        if current_user_entry:
            log.info(f"[Leaderboard] Current user rank: {current_user_entry['rank']}, completion: {current_user_entry['grade_percent']}%")

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
