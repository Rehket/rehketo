from uuid import uuid4

import pytest

from rehketo.permissions.check import (
    PermissionError,
    check_permission,
    permissions_for_roles,
)


def test_admin_has_all_chat_actions():
    perms = permissions_for_roles({"Admin"})
    assert "chat.create_conversation" in perms
    assert "chat.delete_conversation" in perms
    assert "admin.manage_users" in perms


def test_user_has_basic_chat_actions():
    perms = permissions_for_roles({"User"})
    assert "chat.view_conversation" in perms
    assert "chat.write" in perms
    assert "admin.manage_users" not in perms


def test_check_permission_allows():
    assert check_permission({"User"}, "chat.write",
                            resource_type="conversation", resource_id=uuid4())


def test_check_permission_denies():
    assert not check_permission({"User"}, "admin.manage_users",
                                resource_type="system", resource_id=None)


def test_check_permission_rejects_unknown_action():
    with pytest.raises(PermissionError):
        check_permission({"User"}, "not.a.real.action",
                         resource_type=None, resource_id=None)
