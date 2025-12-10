"""
Django app configuration for study_groups
"""

from django.apps import AppConfig


class StudyGroupsConfig(AppConfig):
    """
    Configuration for the study_groups Django app.
    """
    name = 'lms.djangoapps.study_groups'
    verbose_name = 'Study Groups'

    def ready(self):
        """
        Import signal handlers when the app is ready.
        """
        from . import signals  # pylint: disable=unused-import

