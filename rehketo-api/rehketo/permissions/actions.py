"""
Canonical action vocabulary. Any permission check anywhere in the codebase
must reference a name declared here. Adding a new action is a schema change
to the permission surface; think about it as a public API evolution.
"""

ACTIONS: tuple[str, ...] = (
    # Chat domain
    "chat.create_conversation",
    "chat.view_conversation",
    "chat.rename_conversation",
    "chat.delete_conversation",
    "chat.write",
    "chat.cancel_run",
    "chat.upload_files",
    # Admin domain
    "admin.manage_users",
    "admin.view_audit",
)

ACTIONS_SET = frozenset(ACTIONS)
