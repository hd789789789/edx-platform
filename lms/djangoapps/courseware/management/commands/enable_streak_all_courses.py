"""
Django management command to enable streak flags for all existing courses.
This is a one-time script to enable streak for courses that were created before auto-enable was implemented.
"""

from django.core.management.base import BaseCommand
from openedx.core.djangoapps.waffle_utils.models import WaffleFlagCourseOverrideModel
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from lms.djangoapps.courseware.toggles import (
    COURSEWARE_MICROFRONTEND_PROGRESS_MILESTONES,
    COURSEWARE_MICROFRONTEND_PROGRESS_MILESTONES_STREAK_CELEBRATION,
)

class Command(BaseCommand):
    help = 'Enable streak flags for all existing courses. This is a one-time script for courses created before auto-enable.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip courses that already have flags enabled',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']

        flags_to_enable = [
            COURSEWARE_MICROFRONTEND_PROGRESS_MILESTONES.flag_name,
            COURSEWARE_MICROFRONTEND_PROGRESS_MILESTONES_STREAK_CELEBRATION.flag_name,
        ]

        courses = CourseOverview.objects.all()
        total_courses = courses.count()
        
        self.stdout.write(self.style.SUCCESS(f"Found {total_courses} courses to process."))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made."))
        
        enabled_count = 0
        skipped_count = 0
        error_count = 0

        for course in courses:
            course_enabled = True
            course_skipped = False
            
            for flag_name in flags_to_enable:
                # Check if flag already exists
                existing = WaffleFlagCourseOverrideModel.objects.filter(
                    waffle_flag=flag_name,
                    course_id=course.id,
                    enabled=True
                ).first()
                
                if existing:
                    if skip_existing:
                        course_skipped = True
                        continue
                    # Update existing if not enabled
                    if not existing.enabled or existing.override_choice != 'on':
                        if not dry_run:
                            existing.override_choice = 'on'
                            existing.enabled = True
                            existing.note = 'Auto-enabled via enable_streak_all_courses command'
                            existing.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Updated flag {flag_name} for course {course.id}"
                            )
                        )
                else:
                    # Create new override
                    if not dry_run:
                        try:
                            WaffleFlagCourseOverrideModel.objects.create(
                                waffle_flag=flag_name,
                                course_id=course.id,
                                override_choice='on',
                                enabled=True,
                                note='Auto-enabled via enable_streak_all_courses command'
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  Created flag {flag_name} for course {course.id}"
                                )
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"  Error creating flag {flag_name} for course {course.id}: {e}"
                                )
                            )
                            course_enabled = False
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Would create flag {flag_name} for course {course.id}"
                            )
                        )
            
            if course_skipped:
                skipped_count += 1
            elif course_enabled:
                enabled_count += 1
            else:
                error_count += 1
            
            if (enabled_count + skipped_count + error_count) % 10 == 0:
                self.stdout.write(
                    f"Progress: {enabled_count} enabled, {skipped_count} skipped, {error_count} errors"
                )

        self.stdout.write(self.style.SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(self.style.SUCCESS(f"  Total courses: {total_courses}"))
        self.stdout.write(self.style.SUCCESS(f"  Enabled: {enabled_count}"))
        if skip_existing:
            self.stdout.write(self.style.SUCCESS(f"  Skipped (already enabled): {skipped_count}"))
        self.stdout.write(self.style.ERROR(f"  Errors: {error_count}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nThis was a DRY RUN. No changes were made."))
            self.stdout.write(self.style.WARNING("Run without --dry-run to apply changes."))
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ All courses processed!"))
            self.stdout.write(self.style.SUCCESS("Note: New courses will automatically have streak enabled via signal handler."))

