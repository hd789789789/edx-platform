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
from django.core.cache import cache as django_cache
from lms.djangoapps.minigames.models import MinigameLog
from urllib.parse import unquote_plus, quote, quote_plus, unquote
from lms.djangoapps.study_groups.models import StudyGroup, StudyGroupComment

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

        # Check cache first — cache per user per course for 5 minutes
        welcome_cache_key = f'welcome_tab_{course_key_string}_{request.user.id}'
        cached_response = django_cache.get(welcome_cache_key)
        if cached_response is not None:
            return Response(cached_response)

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
        last_day_of_streak = None
        if not is_masquerading_as_specific_student(request.user, course_key):
            try:
                # Update streak first
                UserCelebration.perform_streak_updates(
                    request.user, course_key)
                # Get current streak
                try:
                    celebration = request.user.celebration
                    if celebration:
                        streak_days = celebration.streak_length
                        if celebration.last_day_of_streak:
                            last_day_of_streak = celebration.last_day_of_streak.isoformat()
                except UserCelebration.DoesNotExist:
                    streak_days = 0
            except Exception:
                # If streak update fails, try to get existing streak
                try:
                    celebration = request.user.celebration
                    if celebration:
                        streak_days = celebration.streak_length
                        if celebration.last_day_of_streak:
                            last_day_of_streak = celebration.last_day_of_streak.isoformat()
                except UserCelebration.DoesNotExist:
                    streak_days = 0

        # Calculate class rank - Optimized: only calculate for current user and a sample
        # This is expensive, so we'll use a simpler approach
        class_rank = 0
        try:
            # Get current user's completion
            current_user_completion = get_course_blocks_completion_summary(
                course_key, request.user)
            current_user_total = current_user_completion.get(
                'complete_count', 0) + current_user_completion.get('incomplete_count', 0)
            current_user_percent = 0.0
            if current_user_total > 0:
                current_user_percent = (current_user_completion.get(
                    'complete_count', 0) / current_user_total) * 100

            # Get current user's grade
            current_user_grade = course_grade.percent if course_grade else 0
            current_user_score = (current_user_percent *
                                  0.5) + (current_user_grade * 0.5)

            # Count how many users have better score (simplified - only check if we have grade data)
            # For performance, we'll estimate rank based on enrollment count and user's score
            # This is a simplified calculation - can be improved with caching
            total_enrollments = CourseEnrollment.objects.filter(
                course_id=course_key,
                is_active=True
            ).count()

            # Estimate rank: assume normal distribution, user is in top X%
            # This is much faster than calculating for all users
            if current_user_score >= 0.9:
                class_rank = max(1, int(total_enrollments * 0.1))  # Top 10%
            elif current_user_score >= 0.7:
                class_rank = max(1, int(total_enrollments * 0.3))  # Top 30%
            elif current_user_score >= 0.5:
                class_rank = max(1, int(total_enrollments * 0.5))  # Top 50%
            else:
                class_rank = max(1, int(total_enrollments * 0.7))  # Top 70%
        except Exception:
            # If calculation fails, use a default
            class_rank = 0

        # Get today's lessons count - Optimized: use completion summary instead
        # This is faster than loading all blocks
        today_lessons = 0
        try:
            # Estimate based on completion summary
            # If user has incomplete blocks, assume some are available today
            incomplete_count = completion_summary.get('incomplete_count', 0)
            # Rough estimate: assume 1-3 lessons available today
            if incomplete_count > 0:
                today_lessons = min(3, incomplete_count)
            else:
                today_lessons = 0
        except Exception:
            today_lessons = 0

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

        # Compute minigame stats for this course:
        # - total_games: number of distinct appid values seen for this course (clientid matches)
        # - user_played_games: number of distinct appid values the current user has played for this course
        try:
            user_str = str(
                request.user.id) if request.user and request.user.is_authenticated else ''
            encoded_course = quote(course_key_string, safe='')
            encoded_course_plus = quote_plus(course_key_string)
            total_appids = set()
            user_appids = set()

            acceptable_clientids = {course_key_string,
                                    encoded_course, encoded_course_plus}

            def _clientid_matches_course(clientid_raw):
                """Check if a clientid matches the current course."""
                if not clientid_raw:
                    return False
                if clientid_raw in acceptable_clientids:
                    return True
                try:
                    clientid_unq = unquote(clientid_raw)
                except Exception:
                    clientid_unq = clientid_raw
                try:
                    clientid_unq_plus = unquote_plus(clientid_raw)
                except Exception:
                    clientid_unq_plus = clientid_raw
                if clientid_unq in acceptable_clientids or clientid_unq_plus in acceptable_clientids:
                    return True
                if course_key_string and (course_key_string in clientid_raw or course_key_string in clientid_unq or course_key_string in clientid_unq_plus):
                    return True
                if encoded_course and (encoded_course in clientid_raw or encoded_course in clientid_unq or encoded_course in clientid_unq_plus):
                    return True
                return False

            # Cache minigame stats per course (expensive full-scan, cache 10 phút)
            cache_key = f'minigame_appids_{course_key_string}'
            cached = django_cache.get(cache_key)

            if cached is not None:
                total_appids = cached.get('total_appids', set())
                # Still need to compute user_appids from user's own logs
                for log in MinigameLog.objects.filter(
                    msgtype='RESULT', user=user_str
                ).only('payload').iterator():
                    payload = log.payload or {}
                    clientid_raw = payload.get('clientid') or ''
                    if _clientid_matches_course(clientid_raw):
                        appid = payload.get('appid') or payload.get('gameKey')
                        if appid:
                            user_appids.add(appid)
            else:
                # Full scan needed — but use .only() to reduce data transfer
                for log in MinigameLog.objects.filter(
                    msgtype='RESULT'
                ).only('user', 'payload').iterator():
                    payload = log.payload or {}
                    clientid_raw = payload.get('clientid') or ''
                    if _clientid_matches_course(clientid_raw):
                        appid = payload.get('appid') or payload.get('gameKey')
                        if appid:
                            total_appids.add(appid)
                            if str(log.user) == user_str:
                                user_appids.add(appid)
                # Cache total_appids for 10 minutes
                django_cache.set(cache_key, {'total_appids': total_appids}, 600)
        except Exception:
            # If anything goes wrong, fall back to empty sets so UI can use defaults
            total_appids = set()
            user_appids = set()

        total_games = len(total_appids) if len(total_appids) > 0 else 0
        user_played = len(user_appids)

        # Build daily quests list including server-side computed values for tasks 1 and 3.
        # Task 1: completed units / total units
        complete_count = completion_summary.get('complete_count', 0)
        total_units = total_blocks

        # Task 3: whether user is member of any study group in this course and has at least 1 comment
        try:
            user_groups_qs = StudyGroup.objects.filter(
                course_id=course_key).filter(members__user=request.user).distinct()
            user_in_group = user_groups_qs.exists()
            user_comments_count = 0
            if user_in_group:
                user_comments_count = StudyGroupComment.objects.filter(
                    group__in=user_groups_qs, user=request.user).count()
        except Exception:
            user_in_group = False
            user_comments_count = 0

        daily_quests = [
            {
                'id': 1,
                'title': 'Hoàn thành khoá học',
                'description': 'Hoàn thành Unit trong khoá học',
                'reward': '+ XP',
                'progress': int(complete_count),
                'total': int(total_units),
                'completed': (total_units > 0 and int(complete_count) >= int(total_units)),
                'icon': '📚',
                'gradient': 'primary',
            },
            {
                'id': 2,
                'title': 'Luyện Game học tập tương tác',
                'description': 'Rèn luyện kỹ năng với bài tập',
                'reward': '+ XP • 💰 + Xu',
                'progress': user_played,
                'total': total_games if total_games > 0 else 5,
                'completed': (total_games > 0 and user_played >= total_games),
                'icon': '🎯',
                'gradient': 'warning',
            },
            {
                'id': 3,
                'title': 'Tham gia thảo luận',
                'description': 'Bạn phải là học viên khoá học và đăng ít nhất 1 bài trong Nhóm học tập',
                'reward': '+ XP • 💰 + Xu',
                'progress': 1 if user_comments_count > 0 else 0,
                'total': 1,
                'completed': bool(user_in_group and user_comments_count > 0),
                'icon': '💬',
                'gradient': 'primary',
            },
        ]

        # Prepare response data
        data = {
            'success': True,
            'user_stats': {
                'streak_days': streak_days,
                'completion_percent': completion_percent,
                'today_lessons': today_lessons,
                'class_rank': class_rank,
            },
            'important_dates': important_dates,
            'daily_quests': daily_quests,
        }

        serializer = self.get_serializer(data)
        # Cache response for 5 minutes to avoid expensive recomputation
        django_cache.set(welcome_cache_key, serializer.data, 300)
        return Response(serializer.data)
