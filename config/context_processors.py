"""Shared account context for authenticated application pages."""

from dataio.services.authorization import ADMINISTRATOR, is_role
from people.models import AccountProfile


def account_menu(request):
    if not request.user.is_authenticated:
        return {}

    administrator = is_role(request.user, ADMINISTRATOR)
    role = (
        ADMINISTRATOR
        if administrator
        else request.user.groups.values_list("name", flat=True).first() or "Account"
    )
    try:
        avatar = request.user.account_profile.avatar_data_uri
    except AccountProfile.DoesNotExist:
        avatar = ""

    display_name = request.user.get_full_name().strip() or request.user.get_username()
    return {
        "account_avatar": avatar,
        "account_display_name": display_name,
        "account_initial": display_name[:1].upper(),
        "is_administrator": administrator,
        "user_role": role,
    }
