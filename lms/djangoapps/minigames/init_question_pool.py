#!/usr/bin/env python
"""
Init script to create QuestionPool table on local machine.

This script should be run on the local machine to initialize the QuestionPool table.
It applies the migration to create the table.

Usage:
    python manage.py lms migrate minigames

Or if you need to run it manually:
    python init_question_pool.py
"""

import os
import sys
import django

# Setup Django environment
if __name__ == "__main__":
    # Add the edx-platform directory to the path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms.envs.production')

    django.setup()

    from django.core.management import call_command

    print("Applying migration to create QuestionPool table...")
    try:
        call_command('migrate', 'minigames', verbosity=2)
        print("\n✓ Migration applied successfully!")
        print("QuestionPool table has been created.")
        print("\nAPI endpoints available:")
        print("  GET  /api/minigames/question-pool/mate-ids/     - Get all mate_ids")
        print(
            "  GET  /api/minigames/question-pool/               - List all question pools")
        print(
            "  POST /api/minigames/question-pool/               - Create new question pool")
        print(
            "  GET  /api/minigames/question-pool/{mate_id}/     - Get specific question pool")
        print(
            "  PUT  /api/minigames/question-pool/{mate_id}/     - Update question pool")
        print(
            "  PATCH/api/minigames/question-pool/{mate_id}/     - Partial update question pool")
        print(
            "  DELETE /api/minigames/question-pool/{mate_id}/   - Delete question pool (soft delete)")
    except Exception as e:
        print(f"\n✗ Error applying migration: {e}")
        sys.exit(1)
