"""
Badge Tab Views
"""
import logging
from datetime import datetime

from django.utils import timezone
from edx_django_utils import monitoring as monitoring_utils
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys.edx.keys import CourseKey
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.course_api.blocks.api import get_blocks
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.courses import get_course_with_access
from openedx.core.djangoapps.content.block_structure.api import get_block_structure_manager
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from completion.models import BlockCompletion
from xmodule.modulestore.django import modulestore

from .serializers import BadgeResponseSerializer

log = logging.getLogger(__name__)


class BadgeView(RetrieveAPIView):
    """
    **Use Cases**

        Request badge/completion status for course structure

    **Example Requests**

        GET api/course_home/badge/{course_key}

    **Response Values**

        Body consists of the following fields:

        success: (bool) Whether the request was successful
        course_id: (str) The course key string
        course_name: (str) The course display name
        timestamp: (str) ISO format timestamp
        summary: Object containing badge statistics
        chapters: List of chapter badge objects with nested sections and units
    """

    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)
    serializer_class = BadgeResponseSerializer

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)

        # Enable NR tracing for this view based on course
        monitoring_utils.set_custom_attribute('course_id', course_key_string)
        monitoring_utils.set_custom_attribute('user_id', request.user.id)

        # Check if user has access to course
        course = get_course_with_access(
            request.user, 'load', course_key, check_if_enrolled=False)

        # Check if user is enrolled in the course
        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        is_staff = bool(has_access(request.user, 'staff', course_key))

        if not ((enrollment and enrollment.is_active) or is_staff):
            return Response({'success': False, 'error': 'User not enrolled.'}, status=401)

        # Get course blocks structure
        blocks_data = self._get_course_structure(request.user, course_key, course)
        
        # Get user's completion data
        completions = self._get_user_completions(request.user, course_key)
        
        # Build badge data
        badge_data = self._build_badge_data(blocks_data, completions, course)

        data = {
            'success': True,
            'course_id': course_key_string,
            'course_name': course.display_name,
            'timestamp': timezone.now().isoformat(),
            **badge_data
        }

        serializer = self.get_serializer_class()(data)
        return Response(serializer.data)

    def _get_course_structure(self, user, course_key, course):
        """
        Get the course structure with chapters, sections (sequences), and units (verticals)
        Similar to get_course_outline_block_tree but simplified for badge data
        """
        try:
            # Create course usage key similar to get_course_outline_block_tree
            course_usage_key = modulestore().make_course_usage_key(course_key)
            
            # get_blocks returns a dict with 'blocks' and 'root' keys
            # blocks is a dict mapping block_id -> block_data
            # root is the block_id of the root course block
            # Note: request is required, use self.request from the view
            blocks_response = get_blocks(
                request=self.request,
                usage_key=course_usage_key,
                user=user,
                nav_depth=3,  # Use nav_depth instead of depth='all'
                requested_fields=[
                    'display_name',
                    'type',
                    'children',
                    'completion',
                    'complete',  # Add complete field for completion status
                ],
                block_types_filter=['course', 'chapter', 'sequential', 'vertical'],
            )
            
            if not isinstance(blocks_response, dict):
                log.error(f"[Badge] get_blocks returned unexpected type: {type(blocks_response)}")
                return {'blocks': {}, 'root': None}
            
            blocks = blocks_response.get('blocks', {})
            root = blocks_response.get('root')
            
            log.info(f"[Badge] get_blocks returned {len(blocks)} blocks, root: {root}")
            
            if not root:
                log.warning(f"[Badge] No root block found in response")
                return {'blocks': {}, 'root': None}
            
            if root not in blocks:
                log.warning(f"[Badge] Root block ID '{root}' not found in blocks dict. Available block IDs: {list(blocks.keys())[:5]}...")
                return {'blocks': {}, 'root': None}
            
            log.info(f"[Badge] Successfully loaded {len(blocks)} blocks, root: {root}")
            return {'blocks': blocks, 'root': root}
        except Exception as e:
            log.error(f"[Badge] Error getting course structure: {e}", exc_info=True)
            return {'blocks': {}, 'root': None}

    def _get_user_completions(self, user, course_key):
        """
        Get all block completions for user in this course
        """
        from opaque_keys.edx.keys import UsageKey
        
        completions = BlockCompletion.objects.filter(
            user=user,
            context_key=course_key,
            completion=1.0
        ).values_list('block_key', 'modified')
        
        # Convert to dict with normalized block_key (as string) -> completion_time
        # Normalize all keys to string format for consistent matching
        completion_dict = {}
        for block_key, modified in completions:
            # Normalize block_key to string
            block_key_str = str(block_key)
            completion_dict[block_key_str] = modified
            
            # Also try to normalize using UsageKey to handle different formats
            try:
                usage_key = UsageKey.from_string(block_key_str)
                # Store with both original string and normalized UsageKey string
                completion_dict[str(usage_key)] = modified
            except Exception:
                pass
        
        log.info(f"[Badge] Found {len(completions)} completion records for user {user.id}, normalized to {len(completion_dict)} keys")
        if len(completion_dict) > 0:
            # Log first few keys for debugging
            sample_keys = list(completion_dict.keys())[:3]
            log.info(f"[Badge] Sample completion keys: {sample_keys}")
        
        return completion_dict

    def _build_badge_data(self, blocks_data, completions, course):
        """
        Build badge data structure from course blocks and completion data
        """
        blocks = blocks_data.get('blocks', {})
        root_id = blocks_data.get('root')
        
        if not root_id or root_id not in blocks:
            return {
                'summary': {
                    'total_chapters': 0,
                    'completed_chapters': 0,
                    'total_sections': 0,
                    'completed_sections': 0,
                    'total_units': 0,
                    'completed_units': 0,
                    'completion_percentage': 0.0,
                },
                'chapters': []
            }

        root_block = blocks[root_id]
        chapter_ids = root_block.get('children', [])
        
        chapters = []
        total_chapters = 0
        completed_chapters = 0
        total_sections = 0
        completed_sections = 0
        total_units = 0
        completed_units = 0

        for chapter_id in chapter_ids:
            if chapter_id not in blocks:
                continue
                
            chapter_block = blocks[chapter_id]
            if chapter_block.get('type') != 'chapter':
                continue
            
            total_chapters += 1
            chapter_data = self._build_chapter_data(chapter_id, chapter_block, blocks, completions)
            chapters.append(chapter_data)
            
            if chapter_data['is_completed']:
                completed_chapters += 1
            
            total_sections += chapter_data['total_sections']
            completed_sections += chapter_data['completed_sections']
            
            for section in chapter_data['sections']:
                total_units += section['total_units']
                completed_units += section['completed_units']

        completion_percentage = round(
            (completed_units / total_units * 100) if total_units > 0 else 0.0, 1
        )

        return {
            'summary': {
                'total_chapters': total_chapters,
                'completed_chapters': completed_chapters,
                'total_sections': total_sections,
                'completed_sections': completed_sections,
                'total_units': total_units,
                'completed_units': completed_units,
                'completion_percentage': completion_percentage,
            },
            'chapters': chapters
        }

    def _build_chapter_data(self, chapter_id, chapter_block, blocks, completions):
        """
        Build chapter badge data with nested sections
        """
        section_ids = chapter_block.get('children', [])
        sections = []
        completed_sections_count = 0
        chapter_completed_at = None
        
        for section_id in section_ids:
            if section_id not in blocks:
                continue
                
            section_block = blocks[section_id]
            if section_block.get('type') != 'sequential':
                continue
            
            section_data = self._build_section_data(section_id, section_block, blocks, completions)
            sections.append(section_data)
            
            if section_data['is_completed']:
                completed_sections_count += 1
                # Track latest completion time
                if section_data['completed_at']:
                    section_time = section_data['completed_at']
                    if chapter_completed_at is None or section_time > chapter_completed_at:
                        chapter_completed_at = section_time

        is_completed = len(sections) > 0 and completed_sections_count == len(sections)
        
        return {
            'chapter_id': chapter_id,
            'chapter_name': chapter_block.get('display_name', 'Untitled Chapter'),
            'is_completed': is_completed,
            'completed_at': chapter_completed_at,
            'total_sections': len(sections),
            'completed_sections': completed_sections_count,
            'sections': sections,
        }

    def _build_section_data(self, section_id, section_block, blocks, completions):
        """
        Build section (Bài) badge data with nested units
        """
        unit_ids = section_block.get('children', [])
        units = []
        completed_units_count = 0
        section_completed_at = None
        
        for unit_id in unit_ids:
            if unit_id not in blocks:
                continue
                
            unit_block = blocks[unit_id]
            if unit_block.get('type') != 'vertical':
                continue
            
            unit_data = self._build_unit_data(unit_id, unit_block, completions)
            units.append(unit_data)
            
            if unit_data['is_completed']:
                completed_units_count += 1
                # Track latest completion time
                if unit_data['completed_at']:
                    unit_time = unit_data['completed_at']
                    if section_completed_at is None or unit_time > section_completed_at:
                        section_completed_at = unit_time

        is_completed = len(units) > 0 and completed_units_count == len(units)
        
        return {
            'section_id': section_id,
            'section_name': section_block.get('display_name', 'Untitled Section'),
            'is_completed': is_completed,
            'completed_at': section_completed_at,
            'total_units': len(units),
            'completed_units': completed_units_count,
            'units': units,
        }

    def _build_unit_data(self, unit_id, unit_block, completions):
        """
        Build unit badge data
        """
        from opaque_keys.edx.keys import UsageKey
        
        # Normalize unit_id to string format for matching
        unit_id_str = str(unit_id)
        
        # First, try to get completion from block data itself (if get_blocks provided it)
        # Block may have 'complete' field (boolean) or 'completion' field
        is_completed = unit_block.get('complete', False)
        completed_at = None
        
        # If block doesn't have completion info, check BlockCompletion table
        if not is_completed:
            # Try multiple formats to match with completions
            # First try direct string match
            if unit_id_str in completions:
                is_completed = True
                completed_at = completions.get(unit_id_str)
            else:
                # Try to normalize using UsageKey and match again
                try:
                    usage_key = UsageKey.from_string(unit_id_str)
                    normalized_key = str(usage_key)
                    if normalized_key in completions:
                        is_completed = True
                        completed_at = completions.get(normalized_key)
                except Exception:
                    pass
        
        # If we got completion from block data but no time, try to get from completions dict
        if is_completed and not completed_at:
            if unit_id_str in completions:
                completed_at = completions.get(unit_id_str)
            else:
                try:
                    usage_key = UsageKey.from_string(unit_id_str)
                    normalized_key = str(usage_key)
                    if normalized_key in completions:
                        completed_at = completions.get(normalized_key)
                except Exception:
                    pass
        
        # Format completion time
        if completed_at:
            completed_at = completed_at.isoformat() if hasattr(completed_at, 'isoformat') else str(completed_at)
        
        return {
            'unit_id': unit_id_str,
            'unit_name': unit_block.get('display_name', 'Untitled Unit'),
            'is_completed': is_completed,
            'completed_at': completed_at,
        }

