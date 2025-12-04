"""
Leaderboard Tab Views
"""

from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.http.response import Http404
from django.db.models import Q
from django.utils import timezone
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys.edx.keys import CourseKey
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.course_home_api.leaderboard.serializers import (
    LeaderboardTabSerializer,
    TopGradesSerializer,
    TopProgressSerializer,
)
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
        course = get_course_or_403(
            request.user, 'load', course_key, check_if_enrolled=False)
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
        enrolled_user_ids = list(
            active_enrollments.values_list('user_id', flat=True))
        all_users = User.objects.filter(
            id__in=enrolled_user_ids).select_related('profile')

        # Get persistent course grades for letter grade and passing status
        course_grades = PersistentCourseGrade.objects.filter(
            course_id=course_key,
            user_id__in=enrolled_user_ids
        )
        grades_dict = {grade.user_id: grade for grade in course_grades}

        # Calculate completion percentage for all users
        completion_data = []
        for user in all_users:
            completion_summary = get_course_blocks_completion_summary(
                course_key, user)
            complete_count = completion_summary.get('complete_count', 0)
            incomplete_count = completion_summary.get('incomplete_count', 0)
            locked_count = completion_summary.get('locked_count', 0)
            total_units = complete_count + incomplete_count + locked_count

            completion_percent = (
                complete_count / total_units * 100) if total_units > 0 else 0.0

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
        completion_data.sort(
            key=lambda x: (-x['completion_percent'], x['username']))

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
                # Using completion_percent in grade_percent field
                'grade_percent': entry['completion_percent'],
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
        log.info(
            f"[Leaderboard] Total enrolled users: {len(enrolled_user_ids)}")
        log.info(f"[Leaderboard] Users with grades: {len(grades_dict)}")
        log.info(f"[Leaderboard] Total in leaderboard: {total_students}")
        log.info(
            f"[Leaderboard] Current user found: {current_user_entry is not None}")
        if current_user_entry:
            log.info(
                f"[Leaderboard] Current user rank: {current_user_entry['rank']}, completion: {current_user_entry['grade_percent']}%")

        if current_user_entry:
            percentile = (
                (total_students - current_user_entry['rank']) / total_students * 100) if total_students > 0 else 0
            current_user_rank_info = {
                'rank': current_user_entry['rank'],
                'total_students': total_students,
                'percentile': round(percentile, 2),
            }

        # Get top 3 performers
        top_performers = leaderboard_data[:3] if len(
            leaderboard_data) >= 3 else leaderboard_data

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


class TopGradesView(RetrieveAPIView):
    """
    **Use Cases**

        Request top students by grade for a specific course

    **Example Requests**

        GET api/course_home/top-grades/{course_key}?limit=10

    **Query Parameters**

        limit: (int) Number of top students to return (default: 10)

    **Response Values**

        Body consists of the following fields:

        success: (bool) Whether the request was successful
        course_id: (str) The course key string
        leaderboard_type: (str) Always "grades"
        timestamp: (str) ISO format timestamp
        summary: Object containing:
            total_students: (int) Total number of graded students
            avg_grade: (float) Average grade percentage
            max_grade: (float) Highest grade percentage
            min_grade: (float) Lowest grade percentage
            top_count: (int) Number of students returned
        top_students: List of student objects, each containing:
            rank: (int) Student's rank position
            user_id: (int) Student's user ID
            username: (str) Student's username
            full_name: (str) Student's display name
            grade_percentage: (float) Student's grade percentage (0-100)
            letter_grade: (str) Student's letter grade
            is_passed: (bool) Whether student has passed
            is_current_user: (bool) Whether this entry is the current user

    **Returns**

        * 200 on success with above fields.
        * 401 if the user is not authenticated or not enrolled.
        * 403 if the user does not have access to the course.
    """

    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)
    serializer_class = TopGradesSerializer

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)

        # Get query parameters
        limit = int(request.query_params.get('limit', 10))

        # Enable NR tracing for this view based on course
        monitoring_utils.set_custom_attribute('course_id', course_key_string)
        monitoring_utils.set_custom_attribute('user_id', request.user.id)

        # Check if user has access to course
        course = get_course_or_403(
            request.user, 'load', course_key, check_if_enrolled=False)

        # Check if user is enrolled in the course
        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        is_staff = bool(has_access(request.user, 'staff', course_key))

        if not ((enrollment and enrollment.is_active) or is_staff):
            return Response({'success': False, 'error': 'User not enrolled.'}, status=401)

        # Get all active enrollments for this course
        active_enrollments = CourseEnrollment.objects.filter(
            course_id=course_key,
            is_active=True
        ).select_related('user')
        enrolled_user_ids = list(
            active_enrollments.values_list('user_id', flat=True))
        
        # Tạo dict để map user_id -> enrollment created timestamp (dùng cho tie-breaking)
        enrollment_dict = {e.user_id: e.created for e in active_enrollments}

        import logging
        log = logging.getLogger(__name__)
        log.info(f"[TopGrades] Total enrolled users: {len(enrolled_user_ids)}")

        # Get ALL enrolled users (not just those with grades)
        all_users = User.objects.filter(
            id__in=enrolled_user_ids).select_related('profile')

        # Get persistent course grades - this is the actual grade data
        # Note: PersistentCourseGrade.user_id is IntegerField, not ForeignKey
        course_grades = PersistentCourseGrade.objects.filter(
            course_id=course_key,
            user_id__in=enrolled_user_ids
        )
        grades_dict = {grade.user_id: grade for grade in course_grades}
        log.info(f"[TopGrades] Users with grades: {len(grades_dict)}")

        # Build grades data for ALL enrolled users
        grades_data = []
        for user in all_users:
            grade = grades_dict.get(user.id)

            try:
                display_name = user.profile.name if user.profile.name else user.username
            except Exception:
                display_name = user.username

            # If user has grade record, use it; otherwise show 0%
            if grade:
                # Quy về thang điểm 10: nhân 10 rồi làm tròn 1 chữ số
                grade_percent = round(
                    grade.percent_grade * 10, 1) if grade.percent_grade else 0.0
                letter_grade = grade.letter_grade or ''
                is_passed = grade.passed_timestamp is not None
                passed_date = grade.passed_timestamp.isoformat() if grade.passed_timestamp else None
                # Lấy thời gian đạt điểm (ưu tiên passed_date, nếu không có thì dùng modified)
                grade_time = grade.passed_timestamp if grade.passed_timestamp else grade.modified
                grade_modified = grade.modified.isoformat() if grade.modified else None
            else:
                grade_percent = 0.0
                letter_grade = ''
                is_passed = False
                passed_date = None
                grade_modified = None
                grade_time = None

            # Tie-breaking: nếu grade_time là None, dùng enrollment created hoặc user date_joined
            tie_breaker_time = grade_time
            if not tie_breaker_time:
                tie_breaker_time = enrollment_dict.get(user.id)
            if not tie_breaker_time:
                tie_breaker_time = user.date_joined

            grades_data.append({
                'user_id': user.id,
                'username': user.username,
                'full_name': display_name,
                'grade_percentage': grade_percent,
                'letter_grade': letter_grade,
                'is_passed': is_passed,
                'passed_date': passed_date,
                'grade_modified': grade_modified,
                'grade_time': grade_time,  # Dùng để hiển thị
                'tie_breaker_time': tie_breaker_time,  # Dùng để sort tie-breaking
                'is_current_user': user.id == request.user.id,
            })

        # Sort by grade percentage (highest first), then by time achieved (earlier = better rank)
        # Dùng tie_breaker_time để đảm bảo luôn có giá trị để sort
        grades_data.sort(key=lambda x: (
            -x['grade_percentage'],
            x['tie_breaker_time'] if x['tie_breaker_time'] else timezone.now()
        ))

        # Calculate ranks - KHÔNG có đồng hạng vì đã sort theo tie_breaker_time
        # Mỗi người một rank riêng: ai đạt điểm trước (hoặc enroll trước) thì xếp trên
        all_students_with_rank = []
        current_user_entry = None

        for idx, entry in enumerate(grades_data):
            # Rank = vị trí trong danh sách đã sort (bắt đầu từ 1)
            entry_with_rank = {
                'rank': idx + 1,
                **entry
            }
            all_students_with_rank.append(entry_with_rank)
            
            # Lưu current user entry
            if entry['is_current_user']:
                current_user_entry = entry_with_rank

        # Limit results cho top_students
        top_students = all_students_with_rank[:limit]
        
        # Kiểm tra xem current user có nằm trong top không
        current_user_in_top = any(s.get('is_current_user') for s in top_students)

        # Calculate summary statistics from ALL enrolled students
        # Note: grades are now on scale of 10, so multiply by 10 for percentage display
        all_grades = [g['grade_percentage'] for g in grades_data]
        # Total enrolled, not just those with grades
        total_students = len(enrolled_user_ids)
        avg_grade = round(sum(all_grades) / len(all_grades),
                          1) if all_grades else 0
        max_grade = max(all_grades) if all_grades else 0
        min_grade = min(all_grades) if all_grades else 0
        log.info(
            f"[TopGrades] Stats - total: {total_students}, avg: {avg_grade}, max: {max_grade}")

        data = {
            'success': True,
            'course_id': course_key_string,
            'leaderboard_type': 'grades',
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_students': total_students,
                'avg_grade': avg_grade,
                'max_grade': max_grade,
                'min_grade': min_grade,
                'top_count': len(top_students),
            },
            'top_students': top_students,
            'current_user_entry': current_user_entry if not current_user_in_top else None,
        }

        serializer = self.get_serializer_class()(data)
        return Response(serializer.data)


class TopProgressView(RetrieveAPIView):
    """
    **Use Cases**

        Request top students by progress (completion) for a specific course

    **Example Requests**

        GET api/course_home/top-progress/{course_key}?period=all&limit=10

    **Query Parameters**

        period: (str) Time period filter - 'week', 'month', or 'all' (default: 'all')
        limit: (int) Number of top students to return (default: 10)

    **Response Values**

        Body consists of the following fields:

        success: (bool) Whether the request was successful
        course_id: (str) The course key string
        leaderboard_type: (str) Always "progress"
        period: (str) The time period filter used
        timestamp: (str) ISO format timestamp
        summary: Object containing:
            total_students_with_progress: (int) Total students with progress data
            avg_progress: (float) Average progress percentage
            top_count: (int) Number of students returned
        top_students: List of student objects, each containing:
            rank: (int) Student's rank position
            user_id: (int) Student's user ID
            username: (str) Student's username
            full_name: (str) Student's display name
            progress_percent: (float) Student's completion percentage (0-100)
            is_current_user: (bool) Whether this entry is the current user

    **Returns**

        * 200 on success with above fields.
        * 401 if the user is not authenticated or not enrolled.
        * 403 if the user does not have access to the course.
    """

    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)
    serializer_class = TopProgressSerializer

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)

        # Get query parameters
        period = request.query_params.get('period', 'all')
        limit = int(request.query_params.get('limit', 10))

        # Enable NR tracing for this view based on course
        monitoring_utils.set_custom_attribute('course_id', course_key_string)
        monitoring_utils.set_custom_attribute('user_id', request.user.id)

        # Check if user has access to course
        course = get_course_or_403(
            request.user, 'load', course_key, check_if_enrolled=False)

        # Check if user is enrolled in the course
        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        is_staff = bool(has_access(request.user, 'staff', course_key))

        if not ((enrollment and enrollment.is_active) or is_staff):
            return Response({'success': False, 'error': 'User not enrolled.'}, status=401)

        # Get all active enrollments for this course (no date filter - show all users)
        enrollments_qs = CourseEnrollment.objects.filter(
            course_id=course_key,
            is_active=True
        ).select_related('user')

        # Note: period filter will be used for display purposes only
        # All enrolled users are always included in the leaderboard
        
        # Tạo dict để map user_id -> enrollment created timestamp (dùng cho tie-breaking)
        enrollment_dict = {e.user_id: e.created for e in enrollments_qs}

        enrolled_user_ids = list(
            enrollments_qs.values_list('user_id', flat=True))
        all_users = User.objects.filter(
            id__in=enrolled_user_ids).select_related('profile')

        import logging
        log = logging.getLogger(__name__)
        log.info(
            f"[TopProgress] Total enrolled users: {len(enrolled_user_ids)}")

        # Calculate completion percentage for all users
        progress_data = []
        for user in all_users:
            completion_summary = get_course_blocks_completion_summary(
                course_key, user)
            complete_count = completion_summary.get('complete_count', 0)
            incomplete_count = completion_summary.get('incomplete_count', 0)
            locked_count = completion_summary.get('locked_count', 0)
            total_units = complete_count + incomplete_count + locked_count

            completion_percent = round(
                (complete_count / total_units * 100), 2) if total_units > 0 else 0.0

            # Debug logging for each user
            log.info(
                f"[TopProgress] User {user.username}: complete={complete_count}, "
                f"incomplete={incomplete_count}, locked={locked_count}, "
                f"total={total_units}, percent={completion_percent}%")

            try:
                display_name = user.profile.name if user.profile.name else user.username
            except:
                display_name = user.username

            # Tie-breaking: dùng enrollment created hoặc user date_joined
            tie_breaker_time = enrollment_dict.get(user.id)
            if not tie_breaker_time:
                tie_breaker_time = user.date_joined

            progress_data.append({
                'user_id': user.id,
                'username': user.username,
                'full_name': display_name,
                'progress_percent': completion_percent,
                'tie_breaker_time': tie_breaker_time,  # Dùng để sort tie-breaking
                'is_current_user': user.id == request.user.id,
            })

        # Sort by progress percentage (highest first), then by time enrolled (earlier = better rank)
        progress_data.sort(
            key=lambda x: (
                -x['progress_percent'],
                x['tie_breaker_time'] if x['tie_breaker_time'] else timezone.now()
            ))

        # Calculate ranks - KHÔNG có đồng hạng, mỗi người một rank riêng
        all_students_with_rank = []
        current_user_entry = None

        for idx, entry in enumerate(progress_data):
            entry_with_rank = {
                'rank': idx + 1,
                **entry
            }
            all_students_with_rank.append(entry_with_rank)
            
            # Lưu current user entry
            if entry['is_current_user']:
                current_user_entry = entry_with_rank

        # Limit results cho top_students
        top_students = all_students_with_rank[:limit]
        
        # Kiểm tra xem current user có nằm trong top không
        current_user_in_top = any(s.get('is_current_user') for s in top_students)

        # Calculate summary statistics
        all_progress = [p['progress_percent'] for p in progress_data]
        total_students = len(all_progress)
        avg_progress = round(sum(all_progress) /
                             total_students, 2) if total_students > 0 else 0

        data = {
            'success': True,
            'course_id': course_key_string,
            'leaderboard_type': 'progress',
            'period': period,
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_students_with_progress': total_students,
                'avg_progress': avg_progress,
                'top_count': len(top_students),
            },
            'top_students': top_students,
            'current_user_entry': current_user_entry if not current_user_in_top else None,
        }

        serializer = self.get_serializer_class()(data)
        return Response(serializer.data)
