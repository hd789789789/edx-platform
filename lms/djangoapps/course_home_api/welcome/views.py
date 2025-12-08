"""
Welcome Tab Views
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys.edx.keys import CourseKey
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.djangoapps.student.models import CourseEnrollment, UserCelebration
from lms.djangoapps.course_home_api.utils import get_course_or_403
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.courses import get_course_blocks_completion_summary
from lms.djangoapps.courseware.masquerade import is_masquerading_as_specific_student
from lms.djangoapps.grades.api import CourseGradeFactory
from lms.djangoapps.course_blocks.api import get_course_blocks
from lms.djangoapps.course_blocks.transformers import start_date
from openedx.core.djangoapps.content.block_structure.transformers import BlockStructureTransformers
from openedx.core.djangoapps.content.block_structure.api import get_block_structure_manager
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from openedx.features.content_type_gating.block_transformers import ContentTypeGateTransformer
from openedx.features.enterprise_support.utils import get_enterprise_learner_generic_name

from .serializers import WelcomeTabSerializer

User = get_user_model()


class WelcomeTabView(RetrieveAPIView):
    """
    **Use Cases**

        Request details for the Welcome Tab including user stats, streak, completion, etc.

    **Example Requests**

        GET api/course_home/welcome/{course_key}

    **Response Values**

        Body consists of the following fields:

        user_stats: Object containing user statistics
            streak_days: (int) Current streak length in days
            completion_percent: (float) Course completion percentage
            today_lessons: (int) Number of lessons available today
            class_rank: (int) User's rank in the class (based on completion/grade)

        important_dates: List of important course dates
            date: (str) Date in ISO format
            title: (str) Title of the date event
            status: (str) Status: 'completed', 'upcoming', 'important', 'today', 'future'
            days_left: (int, optional) Days remaining for important dates

        daily_quests: List of daily quests/tasks (placeholder for future implementation)
    """
    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)
    serializer_class = WelcomeTabSerializer

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)

        # Enable NR tracing
        monitoring_utils.set_custom_attribute('course_id', course_key_string)
        monitoring_utils.set_custom_attribute('user_id', request.user.id)

        # Check access
        course = get_course_or_403(
            request.user, 'load', course_key, check_if_enrolled=False)

        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        is_staff = bool(has_access(request.user, 'staff', course_key))

        if not ((enrollment and enrollment.is_active) or is_staff):
            return Response({'success': False, 'error': 'User not enrolled.'}, status=401)

        # Get course overview
        course_overview = CourseOverview.get_from_id(course_key)

        # Get completion summary
        completion_summary = get_course_blocks_completion_summary(
            course_key, request.user)
        total_blocks = completion_summary.get(
            'complete_count', 0) + completion_summary.get('incomplete_count', 0)
        completion_percent = 0.0
        if total_blocks > 0:
            completion_percent = round(
                (completion_summary.get('complete_count', 0) / total_blocks) * 100, 1
            )

        # Get course grade for ranking
        collected_block_structure = get_block_structure_manager(
            course_key).get_collected()
        course_grade = CourseGradeFactory().read(
            request.user, collected_block_structure=collected_block_structure
        )
        course_grade.update(visible_grades_only=True,
                            has_staff_access=is_staff)

        # Get streak data
        streak_days = 0
        if not is_masquerading_as_specific_student(request.user, course_key):
            try:
                # Update streak first
                UserCelebration.perform_streak_updates(
                    request.user, course_key)
                # Get current streak
                try:
                    celebration = request.user.celebration
                    streak_days = celebration.streak_length if celebration else 0
                except UserCelebration.DoesNotExist:
                    streak_days = 0
            except Exception:
                # If streak update fails, try to get existing streak
                try:
                    celebration = request.user.celebration
                    streak_days = celebration.streak_length if celebration else 0
                except UserCelebration.DoesNotExist:
                    streak_days = 0

        # Calculate class rank based on completion percentage
        # Get all active enrollments
        all_enrollments = CourseEnrollment.objects.filter(
            course_id=course_key,
            is_active=True
        ).select_related('user')

        # Calculate completion for all users
        user_completions = []
        for enrollment in all_enrollments:
            user = enrollment.user
            if user.is_anonymous:
                continue

            user_completion = get_course_blocks_completion_summary(
                course_key, user)
            user_total = user_completion.get(
                'complete_count', 0) + user_completion.get('incomplete_count', 0)
            user_percent = 0.0
            if user_total > 0:
                user_percent = (user_completion.get(
                    'complete_count', 0) / user_total) * 100

            # Also consider grade if available
            try:
                user_grade = CourseGradeFactory().read(
                    user, collected_block_structure=collected_block_structure
                )
                user_grade.update(visible_grades_only=True)
                # Combine completion and grade (weighted)
                combined_score = (user_percent * 0.5) + \
                    (user_grade.percent * 0.5)
            except Exception:
                combined_score = user_percent

            user_completions.append({
                'user_id': user.id,
                'score': combined_score,
            })

        # Sort by score descending
        user_completions.sort(key=lambda x: x['score'], reverse=True)

        # Find current user's rank
        class_rank = 1
        for idx, entry in enumerate(user_completions):
            if entry['user_id'] == request.user.id:
                class_rank = idx + 1
                break

        # Get today's lessons count (sequences available today)
        transformers = BlockStructureTransformers()
        transformers += [start_date.StartDateTransformer(),
                         ContentTypeGateTransformer()]
        usage_key = collected_block_structure.root_block_usage_key
        course_blocks = get_course_blocks(
            request.user,
            usage_key,
            transformers=transformers,
            collected_block_structure=collected_block_structure,
        )

        # Count sequences available today
        today_lessons = 0
        now = timezone.now()
        for block_key in course_blocks.get_block_keys():
            # Get block category from block structure
            block_category = course_blocks.get_xblock_field(
                block_key, 'category', None)
            if block_category == 'sequential':
                # Check if sequence is available
                block_start = course_blocks.get_xblock_field(
                    block_key, 'start', None)
                if block_start:
                    if block_start <= now:
                        today_lessons += 1
                else:
                    # No start date means available
                    today_lessons += 1

        # Get important dates from course
        important_dates = []
        if course.start:
            important_dates.append({
                'date': course.start.isoformat(),
                'title': 'Khóa học bắt đầu',
                'status': 'completed' if course.start.date() < timezone.now().date() else 'upcoming',
            })

        if course.end:
            days_left = (course.end.date() - timezone.now().date()).days
            important_dates.append({
                'date': course.end.isoformat(),
                'title': 'Kết thúc khóa học',
                'status': 'important' if 0 < days_left <= 90 else 'future',
                'days_left': days_left if days_left > 0 else None,
            })

        # Add today marker
        important_dates.append({
            'date': timezone.now().isoformat(),
            'title': 'Đang học tập',
            'status': 'today',
        })

        # Sort dates by date
        important_dates.sort(key=lambda x: x['date'])

        # Prepare data
        data = {
            'success': True,
            'user_stats': {
                'streak_days': streak_days,
                'completion_percent': completion_percent,
                'today_lessons': today_lessons,
                'class_rank': class_rank,
            },
            'important_dates': important_dates,
            'daily_quests': [],  # Placeholder for future implementation
        }

        serializer = self.get_serializer(data)
        return Response(serializer.data)
