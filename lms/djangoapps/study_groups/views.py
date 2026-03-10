"""
API views for Study Groups.
"""

import logging
import os
from django.conf import settings

log = logging.getLogger(__name__)
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.http import Http404, FileResponse
from django.utils.translation import gettext as _
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from edx_rest_framework_extensions.paginators import DefaultPagination
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions, status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    CreateAPIView,
    DestroyAPIView,
    ListAPIView,
    RetrieveAPIView,
)
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.courseware.courses import get_course_with_access
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser

from .models import (
    StudyGroup,
    StudyGroupMember,
    StudyGroupComment,
    CommentAttachment,
    CommentReaction,
    StudyGroupInvitation,
    StudyGroupStreak,
)
from .permissions import (
    can_user_create_group,
    can_user_edit_group,
    can_user_delete_group,
    can_user_manage_members,
    can_user_view_group,
    can_user_comment,
    can_user_edit_comment,
    can_user_delete_comment,
    has_course_staff_privileges,
)
from .serializers import (
    StudyGroupSerializer,
    StudyGroupCreateSerializer,
    StudyGroupUpdateSerializer,
    StudyGroupMemberSerializer,
    StudyGroupMemberCreateSerializer,
    CourseEnrollmentUserSerializer,
    StudyGroupCommentSerializer,
    CommentCreateSerializer,
    CommentUpdateSerializer,
    CommentAttachmentSerializer,
    ReactionCreateSerializer,
    CommentReactionSerializer,
    StudyGroupInvitationSerializer,
    StudyGroupInvitationCreateSerializer,
    StudyGroupStreakSerializer,
)

log = logging.getLogger(__name__)


class StudyGroupPagination(DefaultPagination):
    """Pagination for study groups list."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CommentPagination(DefaultPagination):
    """Pagination for comments list."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class StudyGroupListView(ListCreateAPIView):
    """
    List all study groups for a course or create a new study group.
    
    GET /api/courses/{course_id}/study-groups/
    POST /api/courses/{course_id}/study-groups/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = StudyGroupPagination
    
    def get_queryset(self):
        """Get study groups for the course, filtered by user permissions."""
        course_id = self.kwargs.get('course_id')
        user = self.request.user
        
        log.info('Getting study groups list', extra={
            'course_id': course_id,
            'user_id': user.id,
            'username': user.username,
            'method': self.request.method,
        })
        
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError as e:
            log.error('Invalid course ID', extra={
                'course_id': course_id,
                'error': str(e),
            })
            raise Http404(_("Invalid course ID"))
        
        # Verify course exists and user has access
        try:
            get_course_with_access(user, 'load', course_key)
        except Exception as e:
            log.error('Course access denied', extra={
                'course_id': course_id,
                'user_id': user.id,
                'error': str(e),
            })
            raise Http404(_("Course not found or access denied"))
        
        # Get all groups for staff/instructors, or only user's groups for regular users
        is_staff = has_course_staff_privileges(user, course_id)
        if is_staff:
            queryset = StudyGroup.objects.filter(course_id=course_id)
            log.info('User has staff privileges, showing all groups', extra={
                'course_id': course_id,
                'user_id': user.id,
            })
        else:
            # Regular users only see groups they're members of
            queryset = StudyGroup.objects.filter(
                course_id=course_id,
                members__user=user
            ).distinct()
            log.info('Regular user, showing only member groups', extra={
                'course_id': course_id,
                'user_id': user.id,
            })
        
        # Apply search filter if provided
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
            log.info('Applied search filter', extra={
                'course_id': course_id,
                'search_term': search,
            })
        
        count = queryset.count()
        log.info('Study groups queryset prepared', extra={
            'course_id': course_id,
            'count': count,
        })
        
        return queryset.select_related('created_by').prefetch_related('members__user')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on request method."""
        if self.request.method == 'POST':
            return StudyGroupCreateSerializer
        return StudyGroupSerializer
    
    def list(self, request, *args, **kwargs):
        """Override list to add permission info."""
        response = super().list(request, *args, **kwargs)
        course_id = self.kwargs.get('course_id')
        user = request.user
        
        # Add permission info to response
        can_create_group = can_user_create_group(user, course_id)
        
        # Add to response data (works for both paginated and non-paginated responses)
        if isinstance(response.data, dict):
            response.data['can_create_group'] = can_create_group
        
        return response
    
    def perform_create(self, serializer):
        """Create a new study group with permission check."""
        course_id = self.kwargs.get('course_id')
        user = self.request.user
        
        log.info('Creating study group', extra={
            'course_id': course_id,
            'user_id': user.id,
            'username': user.username,
            'data': serializer.validated_data,
        })
        
        if not can_user_create_group(user, course_id):
            log.warning('User does not have permission to create group', extra={
                'course_id': course_id,
                'user_id': user.id,
            })
            raise PermissionDenied(_("You don't have permission to create study groups."))
        
        # Serializer already sets created_by from request context; avoid duplicate kwargs
        serializer.save()
        group = serializer.instance
        
        log.info('Study group created', extra={
            'group_id': group.id,
            'course_id': course_id,
            'user_id': user.id,
        })
        
        # Add creator as admin member (avoid duplicates if already added in serializer)
        membership, created = StudyGroupMember.objects.get_or_create(
            group=group,
            user=user,
            defaults={'role': 'admin'},
        )
        
        if created:
            log.info('Creator added as admin member', extra={
                'group_id': group.id,
                'membership_id': membership.id,
                'user_id': user.id,
            })
        else:
            log.info('Creator already a member, skip adding duplicate', extra={
                'group_id': group.id,
                'user_id': user.id,
            })


class StudyGroupDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a study group.
    
    GET /api/study-groups/{id}/
    PUT /api/study-groups/{id}/
    DELETE /api/study-groups/{id}/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'id'
    
    def get_queryset(self):
        """Get study groups the user can access."""
        user = self.request.user
        queryset = StudyGroup.objects.all()
        
        # Filter by user permissions
        if not has_course_staff_privileges(user, None):
            # Regular users only see their own groups
            queryset = queryset.filter(members__user=user).distinct()
        
        return queryset.select_related('created_by').prefetch_related('members__user')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on request method."""
        if self.request.method in ('PUT', 'PATCH'):
            return StudyGroupUpdateSerializer
        return StudyGroupSerializer
    
    def check_object_permissions(self, request, obj):
        """Check if user has permission to perform the action."""
        log.info('Checking object permissions', extra={
            'group_id': obj.id,
            'user_id': request.user.id,
            'method': request.method,
        })
        
        if request.method == 'GET':
            if not can_user_view_group(request.user, obj):
                log.warning('User does not have permission to view group', extra={
                    'group_id': obj.id,
                    'user_id': request.user.id,
                })
                raise PermissionDenied(_("You don't have permission to view this group."))
        elif request.method in ('PUT', 'PATCH'):
            if not can_user_edit_group(request.user, obj):
                log.warning('User does not have permission to edit group', extra={
                    'group_id': obj.id,
                    'user_id': request.user.id,
                })
                raise PermissionDenied(_("You don't have permission to edit this group."))
        elif request.method == 'DELETE':
            if not can_user_delete_group(request.user, obj):
                log.warning('User does not have permission to delete group', extra={
                    'group_id': obj.id,
                    'user_id': request.user.id,
                })
                raise PermissionDenied(_("You don't have permission to delete this group."))
        
        log.info('Permission check passed', extra={
            'group_id': obj.id,
            'user_id': request.user.id,
            'method': request.method,
        })


class StudyGroupMemberListView(ListCreateAPIView):
    """
    List members of a study group or add a new member.
    
    GET /api/study-groups/{id}/members/
    POST /api/study-groups/{id}/members/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = StudyGroupMemberSerializer
    
    def get_serializer_class(self):
        """Return appropriate serializer based on request method."""
        if self.request.method == 'POST':
            from .serializers import StudyGroupMemberCreateSerializer
            return StudyGroupMemberCreateSerializer
        return StudyGroupMemberSerializer
    
    def get_queryset(self):
        """Get members of the study group."""
        group_id = self.kwargs.get('id')
        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            raise Http404(_("Study group not found"))
        
        # Check view permission
        if not can_user_view_group(self.request.user, group):
            raise PermissionDenied(_("You don't have permission to view this group."))
        
        return StudyGroupMember.objects.filter(group=group).select_related('user')
    
    def perform_create(self, serializer):
        """Add a member to the study group."""
        group_id = self.kwargs.get('id')
        user = self.request.user
        
        log.info('Adding member to study group', extra={
            'group_id': group_id,
            'user_id': user.id,
            'target_user_id': serializer.validated_data.get('user'),
        })
        
        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            log.error('Study group not found', extra={'group_id': group_id})
            raise Http404(_("Study group not found"))
        
        # Check permission
        if not can_user_manage_members(self.request.user, group):
            log.warning('User does not have permission to manage members', extra={
                'group_id': group_id,
                'user_id': user.id,
            })
            raise PermissionDenied(_("You don't have permission to manage members."))
        
        target_user = serializer.validated_data['user']
        
        # Check if user is enrolled in course
        if not CourseEnrollment.is_enrolled(target_user, group.course_id):
            log.warning('Target user is not enrolled in course', extra={
                'group_id': group_id,
                'target_user_id': target_user.id,
                'course_id': str(group.course_id),
            })
            raise ValidationError(_("User must be enrolled in the course."))
        
        # Check if user is already a member
        if StudyGroupMember.objects.filter(group=group, user=target_user).exists():
            log.warning('User is already a member', extra={
                'group_id': group_id,
                'target_user_id': target_user.id,
            })
            raise ValidationError(_("User is already a member of this group."))
        
        membership = serializer.save(group=group)
        
        log.info('Member added successfully', extra={
            'group_id': group_id,
            'membership_id': membership.id,
            'target_user_id': target_user.id,
        })


class StudyGroupMemberDetailView(DestroyAPIView):
    """
    Remove a member from a study group.
    
    DELETE /api/study-groups/{id}/members/{user_id}/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'user_id'
    lookup_url_kwarg = 'user_id'
    
    def get_queryset(self):
        """Get members of the study group."""
        group_id = self.kwargs.get('id')
        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            raise Http404(_("Study group not found"))
        
        # Check permission
        if not can_user_manage_members(self.request.user, group):
            raise PermissionDenied(_("You don't have permission to manage members."))
        
        return StudyGroupMember.objects.filter(group=group)
    
    def get_object(self):
        """Get the membership object to delete."""
        queryset = self.get_queryset()
        user_id = self.kwargs.get('user_id')
        try:
            return queryset.get(user_id=user_id)
        except StudyGroupMember.DoesNotExist:
            raise Http404(_("Member not found"))


class AvailableMembersPagination(DefaultPagination):
    """Pagination for available members list."""
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 50


class AvailableGroupMembersListView(ListAPIView):
    """
    List enrolled users (of the course) who are not yet members of the group.
    
    GET /api/study-groups/{id}/available-members/?search=<query>&page=<n>
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = CourseEnrollmentUserSerializer
    pagination_class = AvailableMembersPagination
    
    def get_queryset(self):
        group_id = self.kwargs.get('id')
        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            raise Http404(_("Study group not found"))
        
        # Permission: only managers can view available members
        if not can_user_manage_members(self.request.user, group):
            raise PermissionDenied(_("You don't have permission to manage members."))
        
        # Users enrolled in course
        enrolled_qs = CourseEnrollment.objects.filter(
            course_id=group.course_id,
            is_active=True,
        ).values_list('user_id', flat=True)
        
        # Exclude existing members
        member_user_ids = StudyGroupMember.objects.filter(group=group).values_list('user_id', flat=True)
        
        User = get_user_model()
        users = User.objects.filter(id__in=enrolled_qs).exclude(id__in=member_user_ids)
        
        search = self.request.query_params.get('search', '').strip()
        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        return users.order_by('username')


class InvitationPagination(DefaultPagination):
    """Pagination for invitations list."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class StudyGroupInvitationListView(ListCreateAPIView):
    """
    List invitations for a study group or create a new invitation.

    GET /api/study-groups/study-groups/{id}/invitations/
    POST /api/study-groups/study-groups/{id}/invitations/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = InvitationPagination

    def get_group(self):
        group_id = self.kwargs.get('id')
        try:
            return StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            raise Http404(_("Study group not found"))

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudyGroupInvitationCreateSerializer
        return StudyGroupInvitationSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method == 'POST':
            context['group'] = self.get_group()
        return context

    def get_queryset(self):
        group = self.get_group()
        if not can_user_manage_members(self.request.user, group):
            raise PermissionDenied(_("You don't have permission to view invitations for this group."))
        status_filter = self.request.query_params.get('status', 'pending')
        return StudyGroupInvitation.objects.filter(
            group=group,
            status=status_filter,
        ).select_related('invited_by', 'invitee', 'group')

    def perform_create(self, serializer):
        group = self.get_group()
        if not can_user_manage_members(self.request.user, group):
            raise PermissionDenied(_("You don't have permission to invite members."))
        invitation = serializer.save()
        log.info('Study group invitation created', extra={
            'invitation_id': invitation.id,
            'group_id': group.id,
            'invited_by': self.request.user.id,
            'invitee': invitation.invitee.id,
        })


class MyInvitationsListView(ListAPIView):
    """
    List pending invitations for the current user.

    GET /api/study-groups/invitations/my/?course_id=...
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = StudyGroupInvitationSerializer
    pagination_class = InvitationPagination

    def get_queryset(self):
        queryset = StudyGroupInvitation.objects.filter(
            invitee=self.request.user,
            status='pending',
        ).select_related('invited_by', 'invitee', 'group')

        course_id = self.request.query_params.get('course_id')
        if course_id:
            try:
                course_key = CourseKey.from_string(course_id)
                queryset = queryset.filter(group__course_id=course_key)
            except InvalidKeyError:
                pass

        return queryset.order_by('-created_at')


class InvitationResponseView(APIView):
    """
    Accept or decline a study group invitation.

    POST /api/study-groups/invitations/{id}/respond/
    Body: {"action": "accept"} or {"action": "decline"}
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, id):
        try:
            invitation = StudyGroupInvitation.objects.select_related('group', 'invitee').get(id=id)
        except StudyGroupInvitation.DoesNotExist:
            raise Http404(_("Invitation not found"))

        if invitation.invitee != request.user:
            raise PermissionDenied(_("You can only respond to your own invitations."))

        if invitation.status != 'pending':
            return Response(
                {'error': _("This invitation has already been responded to.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = request.data.get('action')
        if action not in ('accept', 'decline'):
            return Response(
                {'error': _("Action must be 'accept' or 'decline'.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == 'accept':
            try:
                invitation.accept()
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            log.info('Study group invitation accepted', extra={
                'invitation_id': invitation.id,
                'group_id': invitation.group.id,
                'user_id': request.user.id,
            })
        else:
            invitation.decline()
            log.info('Study group invitation declined', extra={
                'invitation_id': invitation.id,
                'group_id': invitation.group.id,
                'user_id': request.user.id,
            })

        serializer = StudyGroupInvitationSerializer(invitation)
        return Response(serializer.data)


class StudyGroupCommentListView(ListCreateAPIView):
    """
    List comments in a study group or create a new comment.

    GET /api/study-groups/{id}/comments/
    POST /api/study-groups/{id}/comments/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CommentPagination
    serializer_class = StudyGroupCommentSerializer
    
    def get_serializer_context(self):
        """Add request to serializer context for file URLs."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_queryset(self):
        """Get comments for the study group."""
        group_id = self.kwargs.get('id')
        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            raise Http404(_("Study group not found"))
        
        # Check view permission
        if not can_user_view_group(self.request.user, group):
            raise PermissionDenied(_("You don't have permission to view this group."))
        
        # Get top-level comments (no parent)
        queryset = StudyGroupComment.objects.filter(
            group=group,
            parent_comment__isnull=True
        ).select_related('user').prefetch_related(
            'attachments',
            'reactions__user',
            'replies__user',
            'replies__attachments',
            'replies__reactions__user'
        )
        
        # Order by creation date
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on request method."""
        if self.request.method == 'POST':
            return CommentCreateSerializer
        return StudyGroupCommentSerializer
    
    def list(self, request, *args, **kwargs):
        """Override list to log attachments."""
        response = super().list(request, *args, **kwargs)
        
        # Log attachments in response for debugging
        if response.data and 'results' in response.data:
            for comment_data in response.data['results'][:3]:  # Log first 3 comments
                comment_id = comment_data.get('id')
                attachments = comment_data.get('attachments', [])
                
                # Also check the actual comment object from DB
                try:
                    from lms.djangoapps.study_groups.models import StudyGroupComment
                    comment_obj = StudyGroupComment.objects.prefetch_related('attachments').get(id=comment_id)
                    db_attachments_count = comment_obj.attachments.count()
                    db_attachments = list(comment_obj.attachments.values('id', 'file_name', 'file_type'))
                except Exception as e:
                    db_attachments_count = -1
                    db_attachments = []
                    log.warning('Failed to get comment from DB', extra={'comment_id': comment_id, 'error': str(e)})
                
                log.info('Comment in list response', extra={
                    'comment_id': comment_id,
                    'has_attachments_field': 'attachments' in comment_data,
                    'attachments_count_in_response': len(attachments) if isinstance(attachments, list) else 0,
                    'attachments_type': type(attachments).__name__,
                    'attachments_in_response': attachments[:2] if isinstance(attachments, list) and len(attachments) > 0 else [],
                    'db_attachments_count': db_attachments_count,
                    'db_attachments': db_attachments[:2],
                })
        
        return response
    
    def perform_create(self, serializer):
        """Create a new comment."""
        group_id = self.kwargs.get('id')
        user = self.request.user
        
        log.info('Creating comment', extra={
            'group_id': group_id,
            'user_id': user.id,
            'content_length': len(serializer.validated_data.get('content', '')),
        })
        
        try:
            group = StudyGroup.objects.get(id=group_id)
        except StudyGroup.DoesNotExist:
            log.error('Study group not found', extra={'group_id': group_id})
            raise Http404(_("Study group not found"))
        
        # Check permission
        if not can_user_comment(self.request.user, group):
            log.warning('User does not have permission to comment', extra={
                'group_id': group_id,
                'user_id': user.id,
            })
            raise PermissionDenied(_("You don't have permission to comment in this group."))
        
        comment = serializer.save(group=group, user=self.request.user)
        
        log.info('Comment created successfully', extra={
            'comment_id': comment.id,
            'group_id': group_id,
            'user_id': user.id,
        })


class StudyGroupCommentDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a comment.
    
    GET /api/comments/{id}/
    PUT /api/comments/{id}/
    DELETE /api/comments/{id}/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'id'
    serializer_class = StudyGroupCommentSerializer
    
    def get_queryset(self):
        """Get comments the user can access."""
        return StudyGroupComment.objects.select_related(
            'user', 'group'
        ).prefetch_related(
            'attachments',
            'reactions__user',
            'replies__user'
        )
    
    def get_serializer_class(self):
        """Return appropriate serializer based on request method."""
        if self.request.method in ('PUT', 'PATCH'):
            return CommentUpdateSerializer
        return StudyGroupCommentSerializer
    
    def check_object_permissions(self, request, obj):
        """Check if user has permission to perform the action."""
        if request.method == 'GET':
            # Check if user can view the group
            if not can_user_view_group(request.user, obj.group):
                raise PermissionDenied(_("You don't have permission to view this comment."))
        elif request.method in ('PUT', 'PATCH'):
            if not can_user_edit_comment(request.user, obj):
                raise PermissionDenied(_("You don't have permission to edit this comment."))
        elif request.method == 'DELETE':
            if not can_user_delete_comment(request.user, obj):
                raise PermissionDenied(_("You don't have permission to delete this comment."))


class CommentReactionView(APIView):
    """
    Add or remove a reaction to a comment.
    
    POST /api/comments/{id}/reactions/
    DELETE /api/comments/{id}/reactions/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_comment(self, comment_id):
        """Get the comment object."""
        try:
            comment = StudyGroupComment.objects.select_related('group').get(id=comment_id)
        except StudyGroupComment.DoesNotExist:
            raise Http404(_("Comment not found"))
        
        # Check if user can view the group
        if not can_user_view_group(self.request.user, comment.group):
            raise PermissionDenied(_("You don't have permission to view this comment."))
        
        return comment
    
    def post(self, request, comment_id):
        """Add a reaction to a comment."""
        user = request.user
        reaction_type = request.data.get('reaction_type')
        
        log.info('Adding reaction to comment', extra={
            'comment_id': comment_id,
            'user_id': user.id,
            'reaction_type': reaction_type,
        })
        
        comment = self.get_comment(comment_id)
        
        serializer = ReactionCreateSerializer(
            data={
                'comment': comment.id,
                'reaction_type': reaction_type
            },
            context={'request': request}
        )
        
        if serializer.is_valid():
            reaction = serializer.save()
            log.info('Reaction added successfully', extra={
                'reaction_id': reaction.id,
                'comment_id': comment_id,
                'user_id': user.id,
                'reaction_type': reaction_type,
            })
            return Response(
                CommentReactionSerializer(reaction, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        
        log.warning('Invalid reaction data', extra={
            'comment_id': comment_id,
            'errors': serializer.errors,
        })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, comment_id):
        """Remove user's reaction from a comment."""
        comment = self.get_comment(comment_id)
        
        try:
            reaction = CommentReaction.objects.get(
                comment=comment,
                user=request.user
            )
            reaction.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CommentReaction.DoesNotExist:
            return Response(
                {'error': _("Reaction not found")},
                status=status.HTTP_404_NOT_FOUND
            )


class CommentAttachmentView(APIView):
    """
    Upload attachments for a comment.
    
    POST /api/comments/{id}/attachments/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)
    
    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB
    
    # Allowed file extensions
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx'}
    ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.wmv', '.flv'}
    
    def get_comment(self, comment_id):
        """Get the comment object."""
        try:
            comment = StudyGroupComment.objects.select_related('group', 'user').get(id=comment_id)
        except StudyGroupComment.DoesNotExist:
            raise Http404(_("Comment not found"))
        
        # Check if user can view the group
        if not can_user_view_group(self.request.user, comment.group):
            raise PermissionDenied(_("You don't have permission to view this comment."))
        
        # Allow adding attachments if:
        # 1. User is the comment owner, OR
        # 2. User has staff privileges, OR
        # 3. User can edit the comment (which includes owners)
        user = self.request.user
        is_owner = comment.user and comment.user.id == user.id
        has_staff_privileges = has_course_staff_privileges(user, comment.group.course_id)
        can_edit = can_user_edit_comment(user, comment)
        
        if not (is_owner or has_staff_privileges or can_edit):
            raise PermissionDenied(_("You don't have permission to add attachments to this comment."))
        
        return comment
    
    def _delete_file(self, file_field):
        """Safely delete file from storage if exists."""
        try:
            if file_field and file_field.name and file_field.storage.exists(file_field.name):
                file_field.storage.delete(file_field.name)
        except Exception:
            log.warning('Failed to delete attachment file from storage', exc_info=True)
    
    def get_file_type(self, filename):
        """Determine file type from extension."""
        ext = os.path.splitext(filename.lower())[1]
        
        if ext in self.ALLOWED_IMAGE_EXTENSIONS:
            return 'image'
        elif ext in self.ALLOWED_DOCUMENT_EXTENSIONS:
            return 'document'
        elif ext in self.ALLOWED_VIDEO_EXTENSIONS:
            return 'video'
        else:
            return None
    
    def validate_file(self, file_obj, file_type):
        """Validate file size and type."""
        # Check file type
        if file_type is None:
            raise ValidationError(_("File type not allowed."))
        
        # Check file size
        file_size = file_obj.size
        if file_type == 'image' and file_size > self.MAX_IMAGE_SIZE:
            raise ValidationError(_("Image file size exceeds 5MB limit."))
        elif file_type == 'document' and file_size > self.MAX_DOCUMENT_SIZE:
            raise ValidationError(_("Document file size exceeds 10MB limit."))
        elif file_type == 'video' and file_size > self.MAX_VIDEO_SIZE:
            raise ValidationError(_("Video file size exceeds 50MB limit."))
    
    def post(self, request, comment_id):
        """Upload an attachment for a comment."""
        user = request.user
        
        log.info('Uploading attachment for comment', extra={
            'comment_id': comment_id,
            'user_id': user.id,
        })
        
        comment = self.get_comment(comment_id)
        
        if 'file' not in request.FILES:
            log.warning('No file provided in request', extra={
                'comment_id': comment_id,
                'user_id': user.id,
            })
            return Response(
                {'error': _("No file provided")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file_obj = request.FILES['file']
        file_name = file_obj.name
        file_type = self.get_file_type(file_name)
        
        log.info('File upload details', extra={
            'comment_id': comment_id,
            'file_name': file_name,
            'file_size': file_obj.size,
            'file_type': file_type,
        })
        
        try:
            self.validate_file(file_obj, file_type)
        except ValidationError as e:
            log.warning('File validation failed', extra={
                'comment_id': comment_id,
                'file_name': file_name,
                'error': str(e),
            })
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create attachment
        attachment = CommentAttachment.objects.create(
            comment=comment,
            file_name=file_name,
            file_path=file_obj,
            file_type=file_type,
            file_size=file_obj.size
        )
        
        log.info('Attachment created successfully', extra={
            'attachment_id': attachment.id,
            'comment_id': comment_id,
            'file_name': file_name,
            'file_size': file_obj.size,
        })
        
        serializer = CommentAttachmentSerializer(
            attachment,
            context={'request': request}
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentAttachmentDetailView(APIView):
    """
    Retrieve, delete or replace a comment attachment.
    
    DELETE /api/comments/attachments/{id}/
    PUT/PATCH /api/comments/attachments/{id}/ (re-upload file)
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def get_object(self, request, attachment_id):
        try:
            attachment = CommentAttachment.objects.select_related('comment', 'comment__group', 'comment__user').get(id=attachment_id)
        except CommentAttachment.DoesNotExist:
            raise Http404(_("Comment attachment not found"))

        comment = attachment.comment
        user = request.user
        # Permission: owner of comment or staff or can edit comment
        if not (can_user_edit_comment(user, comment) or has_course_staff_privileges(user, comment.group.course_id)):
            raise PermissionDenied(_("You don't have permission to modify this attachment."))
        return attachment

    def delete(self, request, id):
        attachment = self.get_object(request, id)
        log.info('Deleting comment attachment', extra={
            'attachment_id': id,
            'comment_id': attachment.comment_id,
            'user_id': request.user.id,
        })
        try:
            if attachment.file_path and attachment.file_path.name and attachment.file_path.storage.exists(attachment.file_path.name):
                attachment.file_path.storage.delete(attachment.file_path.name)
        except Exception:
            log.warning('Failed to delete attachment file from storage', exc_info=True)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, request, id):
        """
        Replace an attachment file with a new one.
        """
        attachment = self.get_object(request, id)
        user = request.user
        comment = attachment.comment

        if 'file' not in request.FILES:
            return Response({'error': _("No file provided")}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES['file']
        file_name = file_obj.name

        # Reuse validation from CommentAttachmentView
        uploader = CommentAttachmentView()
        uploader.request = request
        file_type = uploader.get_file_type(file_name)
        try:
          uploader.validate_file(file_obj, file_type)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        log.info('Replacing attachment file', extra={
            'attachment_id': id,
            'comment_id': comment.id,
            'user_id': user.id,
            'file_name': file_name,
            'file_type': file_type,
            'file_size': file_obj.size,
        })

        # Delete old file in storage
        try:
            if attachment.file_path and attachment.file_path.name and attachment.file_path.storage.exists(attachment.file_path.name):
                attachment.file_path.storage.delete(attachment.file_path.name)
        except Exception:
            log.warning('Failed to delete old attachment file from storage', exc_info=True)

        # Save new file
        attachment.file_path.save(file_name, file_obj, save=True)
        attachment.file_name = file_name
        attachment.file_type = file_type or attachment.file_type
        attachment.file_size = file_obj.size
        attachment.save(update_fields=['file_path', 'file_name', 'file_type', 'file_size', 'uploaded_at'])

        serializer = CommentAttachmentSerializer(attachment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    patch = put


class AttachmentDownloadView(RetrieveAPIView):
    """
    Download an attachment file.
    
    GET /api/attachments/{id}/download/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'id'
    
    def get_queryset(self):
        """Get attachments the user can access."""
        return CommentAttachment.objects.select_related('comment__group')
    
    def retrieve(self, request, *args, **kwargs):
        """Download the attachment file."""
        attachment = self.get_object()
        
        # Check if user can view the comment's group
        if not can_user_view_group(request.user, attachment.comment.group):
            raise PermissionDenied(_("You don't have permission to download this file."))
        
        if not attachment.file_path:
            raise Http404(_("File not found"))
        
        try:
            response = FileResponse(
                attachment.file_path.open('rb'),
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{attachment.file_name}"'
            return response
        except Exception as e:
            log.error(f"Error downloading attachment {attachment.id}: {str(e)}")
            raise Http404(_("Error downloading file"))


class StudyGroupStreakListView(APIView):
    """
    Get group streaks for all study groups the user is a member of in a course.
    
    GET /api/courses/{course_id}/study-groups/streaks/
    """
    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        """Get group streaks for user's study groups in the course."""
        from datetime import date
        from opaque_keys.edx.keys import CourseKey
        
        course_id = kwargs.get('course_id')
        user = request.user
        
        log.info('Getting group streaks', extra={
            'course_id': course_id,
            'user_id': user.id,
        })
        
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return Response(
                {'error': _("Invalid course ID")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all study groups the user is a member of in this course
        user_groups = StudyGroup.objects.filter(
            course_id=course_key,
            members__user=user
        ).distinct()
        
        today = date.today()
        group_streaks = []
        
        for group in user_groups:
            # Get or create streak for this group
            streak, created = StudyGroupStreak.objects.get_or_create(group=group)
            
            # Update streak based on today's activity
            streak.update_streak(today)
            
            # Refresh from DB to get updated values
            streak.refresh_from_db()
            
            # Serialize the streak object directly
            serializer = StudyGroupStreakSerializer(streak, context={'request': request})
            group_streaks.append(serializer.data)
        
        log.info('Group streaks retrieved', extra={
            'course_id': course_id,
            'user_id': user.id,
            'count': len(group_streaks),
        })
        
        return Response({
            'success': True,
            'groups': group_streaks,
        })

