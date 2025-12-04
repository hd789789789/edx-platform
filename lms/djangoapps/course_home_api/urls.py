"""
Contains all the URLs for the Course Home
"""


from django.conf import settings
from django.urls import re_path

from lms.djangoapps.course_home_api.course_metadata.views import CourseHomeMetadataView
from lms.djangoapps.course_home_api.dates.views import DatesTabView
from lms.djangoapps.course_home_api.outline.views import (
    CourseNavigationBlocksView,
    OutlineTabView,
    dismiss_welcome_message,
    save_course_goal,
    unsubscribe_from_course_goal_by_token,
)
from lms.djangoapps.course_home_api.progress.views import ProgressTabView
from lms.djangoapps.course_home_api.leaderboard.views import (
    LeaderboardTabView,
    TopGradesView,
    TopProgressView,
    TopStreakView,
)
from lms.djangoapps.course_home_api.badge.views import BadgeView

# This API is a BFF ("backend for frontend") designed for the learning MFE. It's not versioned because there is no
# guarantee of stability over time. It may change from one Open edX release to another. Don't write any scripts
# that depend on it.

urlpatterns = []

# URL for Course metadata content
urlpatterns += [
    re_path(
        fr'course_metadata/{settings.COURSE_KEY_PATTERN}',
        CourseHomeMetadataView.as_view(),
        name='course-metadata'
    ),
]

# Dates Tab URLs
urlpatterns += [
    re_path(
        fr'dates/{settings.COURSE_KEY_PATTERN}',
        DatesTabView.as_view(),
        name='dates-tab'
    ),
]

# Outline Tab URLs
urlpatterns += [
    re_path(
        fr'outline/{settings.COURSE_KEY_PATTERN}',
        OutlineTabView.as_view(),
        name='outline-tab'
    ),
    re_path(
        fr'navigation/{settings.COURSE_KEY_PATTERN}',
        CourseNavigationBlocksView.as_view(),
        name='course-navigation'
    ),
    re_path(
        r'dismiss_welcome_message',
        dismiss_welcome_message,
        name='dismiss-welcome-message'
    ),
    re_path(
        r'save_course_goal',
        save_course_goal,
        name='save-course-goal'
    ),
    re_path(
        r'unsubscribe_from_course_goal/(?P<token>[^/]*)$',
        unsubscribe_from_course_goal_by_token,
        name='unsubscribe-from-course-goal'
    ),
]

# Top Grades Leaderboard URLs (MUST be before progress to avoid pattern conflict)
urlpatterns += [
    re_path(
        fr'^top-grades/{settings.COURSE_KEY_PATTERN}$',
        TopGradesView.as_view(),
        name='top-grades'
    ),
]

# Top Progress Leaderboard URLs (MUST be before progress to avoid pattern conflict)
urlpatterns += [
    re_path(
        fr'^top-progress/{settings.COURSE_KEY_PATTERN}$',
        TopProgressView.as_view(),
        name='top-progress'
    ),
]

# Top Streak Leaderboard URLs
urlpatterns += [
    re_path(
        fr'^top-streak/{settings.COURSE_KEY_PATTERN}$',
        TopStreakView.as_view(),
        name='top-streak'
    ),
]

# Progress Tab URLs
urlpatterns += [
    re_path(
        fr'^progress/{settings.COURSE_KEY_PATTERN}/(?P<student_id>[^/]+)$',
        ProgressTabView.as_view(),
        name='progress-tab-other-student'
    ),
    re_path(
        fr'^progress/{settings.COURSE_KEY_PATTERN}$',
        ProgressTabView.as_view(),
        name='progress-tab'
    ),
]

# Leaderboard Tab URLs
urlpatterns += [
    re_path(
        fr'^leaderboard/{settings.COURSE_KEY_PATTERN}$',
        LeaderboardTabView.as_view(),
        name='leaderboard-tab'
    ),
]

# Badge Tab URLs
urlpatterns += [
    re_path(
        fr'^badge/{settings.COURSE_KEY_PATTERN}$',
        BadgeView.as_view(),
        name='badge-tab'
    ),
]
