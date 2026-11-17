from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if username is None or password is None:
            return None

        user_model = get_user_model()
        users = user_model._default_manager.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        )
        if users.count() != 1:
            user_model().set_password(password)
            return None

        user = users.first()
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
