# Permission System Refactor: `require_role` → `check_permission`

## Goal

Decouple route handlers from the permission resolution strategy so that switching from global roles to contextual (per-resource) permissions requires no route-level changes.

## Steps

### 1. Define Permission Strings

Create a central registry of permission actions. Use dotted names like `chat.read`, `chat.write`, `chat.delete`, `members.manage`. Avoid tying these to role names.

### 2. Create a Role-to-Permission Mapping

Map each role to a set of permission strings. This is a lookup table — database-backed eventually, a dict for now.

```python
ROLE_PERMISSIONS = {
    "Admin": {"chat.read", "chat.write", "chat.delete", "members.manage"},
    "Moderator": {"chat.read", "chat.write", "chat.delete"},
    "User": {"chat.read", "chat.write"},
}
```

### 3. Build the `check_permission` Function

Signature should accept a user identity, an action, and an optional resource context:

```python
async def check_permission(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
) -> bool:
```

For now, resolve by looking up the user's roles and checking the mapping. The `resource_type` and `resource_id` params are unused initially but present for the future contextual model.

### 4. Create a `ResolvedPermissions` Dependency

Build a FastAPI dependency that calls `check_permission` and exposes a simple `.can(action, resource_id)` interface:

```python
class ResolvedPermissions:
    def can(self, action: str, resource_id: str | None = None) -> bool:
        ...
```

Inject this into routes via `Depends(resolve_permissions)`.

### 5. Replace `require_role` in Route Handlers

Swap all `Depends(require_role("Admin"))` calls with `Depends(resolve_permissions)` and use `permissions.can("chat.delete", chat_id)` checks inside the handler body.

### 6. Add `workspace_id` Column to Data Models

Add a nullable `workspace_id` (or `org_id`) foreign key to resource tables (`Chat`, etc.) to prepare for scoped permissions without requiring it yet.

## Future Work (Do Not Build Yet)

- Per-workspace role assignments
- Channel/resource-level permission overrides (allow/deny)
- Permission inheritance (workspace admin inherits all child permissions)
- Bitmask optimization if permission checks become a bottleneck