#!/usr/bin/env python
"""
Init script to create StudyGroupStreak table on server.

This script should be run on the server to initialize the StudyGroupStreak table.
It applies the migration to create the table.

Usage:
    python manage.py lms migrate study_groups

Or if you need to run it manually:
    python init_group_streaks.py
"""

import os
import sys
import django

# Setup Django environment
if __name__ == "__main__":
    # Add the edx-platform directory to the path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
    
    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms.envs.production')
    
    django.setup()
    
    from django.core.management import call_command
    
    print("Applying migration to create StudyGroupStreak table...")
    try:
        call_command('migrate', 'study_groups', verbosity=2)
        print("\n✓ Migration applied successfully!")
        print("StudyGroupStreak table has been created.")
    except Exception as e:
        print(f"\n✗ Error applying migration: {e}")
        sys.exit(1)


