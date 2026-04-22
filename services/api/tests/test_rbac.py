"""RBAC system tests.

cursor.stage: compliance
cursor.jurisdiction: NJ
cursor.sources: []

Tests the role-based access control implementation from 05_rbac.md.
"""

import pytest

from dcs_api.auth.rbac import CurrentUser, Permissions


class TestCurrentUser:
    """Test CurrentUser permission checks."""

    def test_owner_has_all_permissions(self) -> None:
        """Test that owner role grants all permissions."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="owner@example.com",
            roles=["owner"],
            permissions=set(),
            is_owner=True,
            is_master=False,
        )

        # Owner should pass any permission check
        assert user.has_permission(Permissions.VIEW_ALL_ACCOUNTS)
        assert user.has_permission(Permissions.CONFIGURE_RETENTION)
        assert user.has_permission(Permissions.LIFT_BREACH_LOCKDOWN)

    def test_collector_limited_permissions(self) -> None:
        """Test collector role has limited permissions."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="collector@example.com",
            roles=["collector"],
            permissions={
                Permissions.VIEW_ASSIGNED_ACCOUNTS,
                Permissions.EDIT_ACCOUNT_CONTACT,
                Permissions.CREATE_OUTBOUND_CONTACT,
                Permissions.MANAGE_DISPUTES,
            },
            is_owner=False,
            is_master=False,
        )

        # Collector should have assigned permissions
        assert user.has_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS)
        assert user.has_permission(Permissions.MANAGE_DISPUTES)

        # Collector should NOT have elevated permissions
        assert not user.has_permission(Permissions.VIEW_ALL_ACCOUNTS)
        assert not user.has_permission(Permissions.CONFIGURE_RETENTION)
        assert not user.has_permission(Permissions.MANAGE_USERS)

    def test_supervisor_elevated_permissions(self) -> None:
        """Test supervisor has elevated permissions over collector."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="supervisor@example.com",
            roles=["supervisor"],
            permissions={
                Permissions.VIEW_ASSIGNED_ACCOUNTS,
                Permissions.VIEW_ALL_ACCOUNTS,
                Permissions.EDIT_ACCOUNT_CONTACT,
                Permissions.EDIT_BALANCES_FEES,
                Permissions.CREATE_OUTBOUND_CONTACT,
                Permissions.MANAGE_DISPUTES,
                Permissions.APPROVE_DISPUTE_RESOLUTION,
            },
            is_owner=False,
            is_master=False,
        )

        # Supervisor should have all collector permissions plus more
        assert user.has_permission(Permissions.VIEW_ALL_ACCOUNTS)
        assert user.has_permission(Permissions.APPROVE_DISPUTE_RESOLUTION)

    def test_legal_role_permissions(self) -> None:
        """Test legal reviewer role permissions."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="legal@example.com",
            roles=["legal"],
            permissions={
                Permissions.VIEW_ASSIGNED_ACCOUNTS,
                Permissions.VIEW_ALL_ACCOUNTS,
                Permissions.MANAGE_DISPUTES,
                Permissions.APPROVE_DISPUTE_RESOLUTION,
                Permissions.CREATE_LITIGATION,
                Permissions.APPROVE_LITIGATION_FILINGS,
            },
            is_owner=False,
            is_master=False,
        )

        # Legal should have litigation permissions
        assert user.has_permission(Permissions.CREATE_LITIGATION)
        assert user.has_permission(Permissions.APPROVE_LITIGATION_FILINGS)

        # Legal should NOT have outbound contact permissions
        assert not user.has_permission(Permissions.CREATE_OUTBOUND_CONTACT)

    def test_admin_user_management(self) -> None:
        """Test admin role can manage users."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="admin@example.com",
            roles=["admin"],
            permissions={
                Permissions.VIEW_ALL_ACCOUNTS,
                Permissions.MANAGE_USERS,
                Permissions.CREATE_CUSTOM_ROLES,
                Permissions.CONFIGURE_INTEGRATIONS,
            },
            is_owner=False,
            is_master=False,
        )

        # Admin should have user management
        assert user.has_permission(Permissions.MANAGE_USERS)
        assert user.has_permission(Permissions.CONFIGURE_INTEGRATIONS)

        # Admin should NOT have owner-only permissions
        assert not user.has_permission(Permissions.ASSIGN_OWNER_PERMISSIONS)
        assert not user.has_permission(Permissions.CONFIGURE_RETENTION)

    def test_master_account_metadata_only(self) -> None:
        """Test master account can only view metadata, not consumer data."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="master@example.com",
            roles=["master"],
            permissions={
                Permissions.VIEW_TENANT_METADATA,
                Permissions.LIFT_BREACH_LOCKDOWN,
            },
            is_owner=False,
            is_master=True,
        )

        # Master should have metadata access
        assert user.has_permission(Permissions.VIEW_TENANT_METADATA)
        assert user.has_permission(Permissions.LIFT_BREACH_LOCKDOWN)

        # Master should NOT have consumer data access
        assert not user.has_permission(Permissions.VIEW_ASSIGNED_ACCOUNTS)
        assert not user.has_permission(Permissions.VIEW_ALL_ACCOUNTS)

    def test_has_any_permission(self) -> None:
        """Test checking for any of multiple permissions."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="test@example.com",
            roles=["collector"],
            permissions={Permissions.VIEW_ASSIGNED_ACCOUNTS},
            is_owner=False,
            is_master=False,
        )

        # Should pass if ANY permission matches
        assert user.has_any_permission([
            Permissions.VIEW_ASSIGNED_ACCOUNTS,
            Permissions.VIEW_ALL_ACCOUNTS,
        ])

        # Should fail if NONE match
        assert not user.has_any_permission([
            Permissions.MANAGE_USERS,
            Permissions.CONFIGURE_INTEGRATIONS,
        ])

    def test_has_all_permissions(self) -> None:
        """Test checking for all of multiple permissions."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="test@example.com",
            roles=["supervisor"],
            permissions={
                Permissions.VIEW_ASSIGNED_ACCOUNTS,
                Permissions.VIEW_ALL_ACCOUNTS,
            },
            is_owner=False,
            is_master=False,
        )

        # Should pass if ALL permissions match
        assert user.has_all_permissions([
            Permissions.VIEW_ASSIGNED_ACCOUNTS,
            Permissions.VIEW_ALL_ACCOUNTS,
        ])

        # Should fail if ANY permission is missing
        assert not user.has_all_permissions([
            Permissions.VIEW_ALL_ACCOUNTS,
            Permissions.MANAGE_USERS,
        ])

    def test_has_role(self) -> None:
        """Test role check."""
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            tenant_id="00000000-0000-0000-0000-000000000002",
            email="test@example.com",
            roles=["collector", "supervisor"],
            permissions=set(),
            is_owner=False,
            is_master=False,
        )

        assert user.has_role("collector")
        assert user.has_role("supervisor")
        assert not user.has_role("admin")
