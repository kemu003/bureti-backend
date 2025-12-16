# users/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

UserModel = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that supports both email and username
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user with either username or email
        """
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        # Check if the input is an email or username
        if '@' in username:
            # It's an email - look up by email
            try:
                user = UserModel.objects.get(email=username)
            except UserModel.DoesNotExist:
                # Run the default password hasher once to reduce timing difference
                UserModel().set_password(password)
                return None
        else:
            # It's a username - look up by username
            try:
                user = UserModel.objects.get(username=username)
            except UserModel.DoesNotExist:
                # Run the default password hasher once to reduce timing difference
                UserModel().set_password(password)
                return None
        
        # Check password and user permissions
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
    
    def get_user(self, user_id):
        """
        Get user by ID
        """
        try:
            user = UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        
        return user if self.user_can_authenticate(user) else None


class CaseInsensitiveModelBackend(EmailOrUsernameModelBackend):
    """
    Extended backend that supports case-insensitive email/username
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with case-insensitive username/email
        """
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        # Normalize username to lowercase for comparison
        username_lower = username.lower() if username else ''
        
        # Try to find user by email (case-insensitive)
        if '@' in username_lower:
            try:
                user = UserModel.objects.get(email__iexact=username_lower)
            except UserModel.DoesNotExist:
                try:
                    # Also try case-insensitive username if email not found
                    user = UserModel.objects.get(username__iexact=username_lower)
                except UserModel.DoesNotExist:
                    UserModel().set_password(password)
                    return None
        else:
            # Try case-insensitive username
            try:
                user = UserModel.objects.get(username__iexact=username_lower)
            except UserModel.DoesNotExist:
                try:
                    # Also try case-insensitive email if username not found
                    user = UserModel.objects.get(email__iexact=username_lower)
                except UserModel.DoesNotExist:
                    UserModel().set_password(password)
                    return None
        
        # Check password and user permissions
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None