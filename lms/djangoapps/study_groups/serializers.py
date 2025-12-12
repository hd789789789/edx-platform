"""
Serializers for Study Groups API.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from openedx.core.djangoapps.user_api.accounts.serializers import UserReadOnlySerializer
from openedx.core.lib.api.fields import ExpandableField
from openedx.core.lib.api.serializers import CollapsedReferenceSerializer

from .models import (
    StudyGroup,
    StudyGroupMember,
    StudyGroupComment,
    CommentAttachment,
    CommentReaction,
    StudyGroupStreak,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user information in study groups."""
    
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = fields


class StudyGroupMemberSerializer(serializers.ModelSerializer):
    """Serializer for study group membership."""
    
    user = ExpandableField(
        collapsed_serializer=CollapsedReferenceSerializer(
            model_class=User,
            id_source='username',
            view_name='accounts_api',
            read_only=True,
        ),
        expanded_serializer=UserReadOnlySerializer(),
    )
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    
    class Meta:
        model = StudyGroupMember
        fields = ('id', 'user', 'user_id', 'role', 'joined_at')
        read_only_fields = ('id', 'user_id', 'joined_at')


class StudyGroupMemberCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating study group membership."""
    
    user = serializers.CharField(help_text="Username or email of the user to add")
    
    class Meta:
        model = StudyGroupMember
        fields = ('user', 'role')
    
    def validate_user(self, value):
        """Validate and find user by username or email."""
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        
        User = get_user_model()
        try:
            # Try to find user by username or email
            user = User.objects.get(Q(username=value) | Q(email=value))
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError(_("User not found with username or email: {}").format(value))
        except User.MultipleObjectsReturned:
            raise serializers.ValidationError(_("Multiple users found with username or email: {}").format(value))


class CourseEnrollmentUserSerializer(serializers.ModelSerializer):
    """Serializer for enrolled users to add to study group."""
    
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'full_name')
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class CommentAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for comment attachments."""
    
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CommentAttachment
        fields = ('id', 'file_name', 'file_url', 'file_type', 'file_size', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')
    
    def get_file_url(self, obj):
        """Get the URL to access the file."""
        if obj.file_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_path.url)
            return obj.file_path.url
        return None


class CommentReactionSerializer(serializers.ModelSerializer):
    """Serializer for comment reactions."""
    
    user = ExpandableField(
        collapsed_serializer=CollapsedReferenceSerializer(
            model_class=User,
            id_source='username',
            view_name='accounts_api',
            read_only=True,
        ),
        expanded_serializer=UserReadOnlySerializer(),
    )
    
    class Meta:
        model = CommentReaction
        fields = ('id', 'user', 'reaction_type', 'created_at')
        read_only_fields = ('id', 'created_at')


class ReactionCountSerializer(serializers.Serializer):
    """Serializer for reaction counts."""
    
    reaction_type = serializers.CharField()
    count = serializers.IntegerField()


class StudyGroupCommentSerializer(serializers.ModelSerializer):
    """Serializer for study group comments."""
    
    user = ExpandableField(
        collapsed_serializer=CollapsedReferenceSerializer(
            model_class=User,
            id_source='username',
            view_name='accounts_api',
            read_only=True,
        ),
        expanded_serializer=UserReadOnlySerializer(),
    )
    attachments = CommentAttachmentSerializer(many=True, read_only=True)
    reactions = CommentReactionSerializer(many=True, read_only=True)
    reaction_counts = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyGroupComment
        fields = (
            'id', 'group', 'user', 'parent_comment', 'content',
            'created_at', 'updated_at', 'attachments', 'reactions',
            'reaction_counts', 'user_reaction', 'replies_count',
            'can_edit', 'can_delete'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_reaction_counts(self, obj):
        """Get counts of each reaction type."""
        counts = {}
        for reaction_type, _ in CommentReaction.REACTION_TYPES:
            counts[reaction_type] = obj.reactions.filter(reaction_type=reaction_type).count()
        return counts
    
    def get_user_reaction(self, obj):
        """Get the current user's reaction, if any."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            reaction = obj.reactions.filter(user=request.user).first()
            if reaction:
                return reaction.reaction_type
        return None
    
    def get_replies_count(self, obj):
        """Get the number of replies to this comment."""
        return obj.replies.count()
    
    def get_can_edit(self, obj):
        """Check if current user can edit this comment."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_edit(request.user)
        return False
    
    def get_can_delete(self, obj):
        """Check if current user can delete this comment."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_delete(request.user)
        return False


class StudyGroupSerializer(serializers.ModelSerializer):
    """Serializer for study groups."""
    
    created_by = ExpandableField(
        collapsed_serializer=CollapsedReferenceSerializer(
            model_class=User,
            id_source='username',
            view_name='accounts_api',
            read_only=True,
        ),
        expanded_serializer=UserReadOnlySerializer(),
    )
    members = StudyGroupMemberSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_manage_members = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyGroup
        fields = (
            'id', 'course_id', 'name', 'description', 'created_by',
            'created_at', 'updated_at', 'members', 'member_count',
            'is_member', 'user_role', 'can_edit', 'can_delete',
            'can_manage_members'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_member_count(self, obj):
        """Get the number of members."""
        return obj.get_member_count()
    
    def get_is_member(self, obj):
        """Check if current user is a member."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_member(request.user)
        return False
    
    def get_user_role(self, obj):
        """Get the current user's role in the group."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_user_role(request.user)
        return None
    
    def get_can_edit(self, obj):
        """Check if current user can edit this group."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .permissions import can_user_edit_group
            return can_user_edit_group(request.user, obj)
        return False
    
    def get_can_delete(self, obj):
        """Check if current user can delete this group."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .permissions import can_user_delete_group
            return can_user_delete_group(request.user, obj)
        return False
    
    def get_can_manage_members(self, obj):
        """Check if current user can manage members."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .permissions import can_user_manage_members
            return can_user_manage_members(request.user, obj)
        return False


class StudyGroupCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating study groups."""
    
    class Meta:
        model = StudyGroup
        fields = ('course_id', 'name', 'description')
    
    def create(self, validated_data):
        """Create a new study group."""
        request = self.context.get('request')
        group = StudyGroup.objects.create(
            **validated_data,
            created_by=request.user if request else None
        )
        # Add creator as admin member
        if request and request.user.is_authenticated:
            StudyGroupMember.objects.create(
                group=group,
                user=request.user,
                role='admin'
            )
        return group


class StudyGroupUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating study groups."""
    
    class Meta:
        model = StudyGroup
        fields = ('name', 'description')


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments."""
    
    class Meta:
        model = StudyGroupComment
        fields = ('group', 'parent_comment', 'content')
        extra_kwargs = {
            'group': {'required': False},
        }
    
    def validate_group(self, value):
        """Validate that user can comment in this group."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .permissions import can_user_comment
            if not can_user_comment(request.user, value):
                raise serializers.ValidationError(
                    "You don't have permission to comment in this group."
                )
        return value


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating comments."""
    
    class Meta:
        model = StudyGroupComment
        fields = ('content',)


class ReactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reactions."""
    
    class Meta:
        model = CommentReaction
        fields = ('comment', 'reaction_type')
    
    def validate_reaction_type(self, value):
        """Validate reaction type."""
        valid_types = [choice[0] for choice in CommentReaction.REACTION_TYPES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid reaction type. Must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def create(self, validated_data):
        """Create or update reaction."""
        request = self.context.get('request')
        comment = validated_data['comment']
        reaction_type = validated_data['reaction_type']
        
        # Delete existing reaction if any
        CommentReaction.objects.filter(
            comment=comment,
            user=request.user
        ).delete()
        
        # Create new reaction
        return CommentReaction.objects.create(
            comment=comment,
            user=request.user,
            reaction_type=reaction_type
        )


class StudyGroupStreakSerializer(serializers.Serializer):
    """Serializer for study group streak information."""
    
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    streakDays = serializers.IntegerField(source='streak_length')
    members = serializers.SerializerMethodField()
    additionalMembers = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    
    def get_id(self, obj):
        """Get group ID."""
        return obj.group.id
    
    def get_name(self, obj):
        """Get group name."""
        return obj.group.name
    
    def get_members(self, obj):
        """Get first 3 members for display."""
        from datetime import date
        from common.djangoapps.student.models import UserCelebration
        
        members = obj.group.members.all()[:3]
        today = date.today()
        result = []
        
        for member in members:
            # Get user's initial
            user = member.user
            initial = (user.first_name[0] if user.first_name else '') + (user.last_name[0] if user.last_name else '')
            if not initial:
                initial = user.username[0:2].upper()
            
            # Generate color based on user ID
            num = (user.id or 1) * 2654435761
            # Convert to unsigned 32-bit integer and extract RGB
            num_unsigned = num & 0xFFFFFFFF
            color_hex = format(num_unsigned, '06x')[:6]
            color = f"#{color_hex}"
            
            result.append({
                'id': user.id,
                'initial': initial,
                'color': color,
            })
        
        return result
    
    def get_additionalMembers(self, obj):
        """Get count of additional members beyond the first 3."""
        total = obj.group.members.count()
        return max(0, total - 3)
    
    def get_status(self, obj):
        """Get status: 'all_completed' if all members studied today, 'in_progress' otherwise."""
        from datetime import date
        today = date.today()
        if obj.check_all_members_studied_today(today):
            return 'all_completed'
        return 'in_progress'
    
    def get_message(self, obj):
        """Get message based on status."""
        status = self.get_status(obj)
        if status == 'all_completed':
            return '✓ Tất cả thành viên đã học hôm nay'
        return '💪 Tiếp tục học hôm nay để giữ chuỗi nhóm!'

