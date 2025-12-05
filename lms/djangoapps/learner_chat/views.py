"""
Views for Learner Chat API
"""
import re
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.course_home_api.utils import get_course_or_403
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from .models import ChatRoom, ChatMessage
from .serializers import ChatMessageSerializer, ChatRoomSerializer

User = get_user_model()


class ChatRoomViewSet(ViewSet):
    """
    ViewSet for managing chat rooms and messages
    """
    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)

    def get_room(self, course_key_string, chat_type):
        """Get or create a chat room for a course and chat type"""
        course_key = CourseKey.from_string(course_key_string)
        room, created = ChatRoom.objects.get_or_create(
            course_id=course_key,
            chat_type=chat_type,
            defaults={}
        )
        return room

    def check_course_access(self, request, course_key_string):
        """Check if user has access to the course"""
        course_key = CourseKey.from_string(course_key_string)
        
        # Check course access
        get_course_or_403(request.user, 'load', course_key, check_if_enrolled=False)
        
        # Check enrollment
        enrollment = CourseEnrollment.get_enrollment(request.user, course_key)
        is_staff = bool(has_access(request.user, 'staff', course_key))
        
        if not ((enrollment and enrollment.is_active) or is_staff):
            return False
        return True

    def list_messages(self, request, course_key_string=None, chat_type=None):
        """
        Get messages for a chat room
        
        GET /api/learner_chat/{course_key_string}/{chat_type}/messages/
        """
        if not self.check_course_access(request, course_key_string):
            return Response(
                {'error': 'User not enrolled in course'},
                status=status.HTTP_403_FORBIDDEN
            )

        room = self.get_room(course_key_string, chat_type)
        
        # Get messages (not deleted)
        messages = ChatMessage.objects.filter(
            room=room,
            is_deleted=False
        ).select_related('user').prefetch_related('mentions')[:100]  # Last 100 messages
        
        serializer = ChatMessageSerializer(
            messages,
            many=True,
            context={'request': request}
        )
        
        return Response({
            'room_id': room.id,
            'course_id': course_key_string,
            'chat_type': chat_type,
            'messages': serializer.data
        })

    def create_message(self, request, course_key_string=None, chat_type=None):
        """
        Create a new chat message
        
        POST /api/learner_chat/{course_key_string}/{chat_type}/messages/
        """
        if not self.check_course_access(request, course_key_string):
            return Response(
                {'error': 'User not enrolled in course'},
                status=status.HTTP_403_FORBIDDEN
            )

        room = self.get_room(course_key_string, chat_type)
        message_text = request.data.get('message', '').strip()
        
        if not message_text:
            return Response(
                {'error': 'Message cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract mentions from message (@username)
        mention_pattern = r'@(\w+)'
        mentioned_usernames = re.findall(mention_pattern, message_text)
        mention_ids = []
        
        if mentioned_usernames:
            mentioned_users = User.objects.filter(username__in=mentioned_usernames)
            mention_ids = list(mentioned_users.values_list('id', flat=True))

        # Create message directly
        message = ChatMessage.objects.create(
            room=room,
            user=request.user,
            message=message_text
        )
        
        # Add mentions
        if mention_ids:
            mentioned_users = User.objects.filter(id__in=mention_ids)
            message.mentions.set(mentioned_users)
        
        response_serializer = ChatMessageSerializer(
            message,
            context={'request': request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def delete_message(self, request, course_key_string=None, chat_type=None, message_id=None):
        """
        Delete a chat message (soft delete)
        
        DELETE /api/learner_chat/{course_key_string}/{chat_type}/messages/{message_id}/
        """
        if not self.check_course_access(request, course_key_string):
            return Response(
                {'error': 'User not enrolled in course'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            message = ChatMessage.objects.get(id=message_id, is_deleted=False)
        except ChatMessage.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions: admin can delete any message, users can only delete their own
        is_admin = request.user.is_staff
        is_owner = message.user == request.user

        if not (is_admin or is_owner):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Soft delete
        message.is_deleted = True
        message.deleted_by = request.user
        message.deleted_at = timezone.now()
        message.save()

        return Response({'success': True, 'message': 'Message deleted'}, status=status.HTTP_200_OK)

