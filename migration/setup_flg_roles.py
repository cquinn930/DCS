#!/usr/bin/env python3
"""Set up roles and permissions for the FLG tenant by copying from the sample tenant."""

import asyncio
import uuid

import asyncpg


async def setup_roles():
    conn = await asyncpg.connect("postgresql://dcs:dcs@localhost:5432/dcs")

    tid = await conn.fetchval("SELECT id FROM tenants WHERE slug='flg'")
    if not tid:
        print("ERROR: FLG tenant not found")
        await conn.close()
        return

    admin_id = await conn.fetchval(
        "SELECT id FROM users WHERE email=$1 AND tenant_id=$2",
        "admin@falonilaw.com", tid,
    )
    if not admin_id:
        print("ERROR: admin user not found")
        await conn.close()
        return

    # Clean up any partial roles from previous attempts
    existing = await conn.fetch("SELECT id FROM roles WHERE tenant_id=$1", tid)
    for r in existing:
        await conn.execute("DELETE FROM role_permissions WHERE role_id=$1", r["id"])
        await conn.execute("DELETE FROM user_roles WHERE role_id=$1", r["id"])
    await conn.execute("DELETE FROM roles WHERE tenant_id=$1", tid)
    print(f"Cleaned up {len(existing)} old roles")

    # Find sample tenant to copy from
    sample_tid = await conn.fetchval("SELECT id FROM tenants WHERE slug != 'flg' LIMIT 1")
    if not sample_tid:
        print("ERROR: No sample tenant found to copy roles from")
        await conn.close()
        return

    # Copy roles
    roles = await conn.fetch(
        "SELECT id, name, description, role_type, is_system FROM roles WHERE tenant_id=$1",
        sample_tid,
    )
    role_map = {}
    for r in roles:
        new_id = uuid.uuid4()
        role_map[r["id"]] = (new_id, r["name"])
        await conn.execute(
            "INSERT INTO roles (id, tenant_id, name, description, role_type, is_system) "
            "VALUES ($1,$2,$3,$4,$5,$6)",
            new_id, tid, r["name"], r["description"], r["role_type"], r["is_system"],
        )
    print(f"Created {len(roles)} roles")

    # Copy permissions for each role
    for old_rid, (new_rid, rname) in role_map.items():
        perms = await conn.fetch(
            "SELECT permission_id FROM role_permissions WHERE role_id=$1", old_rid,
        )
        for p in perms:
            await conn.execute(
                "INSERT INTO role_permissions (id, role_id, permission_id) VALUES ($1,$2,$3)",
                uuid.uuid4(), new_rid, p["permission_id"],
            )
        print(f"  {rname}: {len(perms)} permissions")

    # Find admin role
    admin_role_id = None
    for old_rid, (new_rid, rname) in role_map.items():
        if "admin" in rname.lower():
            admin_role_id = new_rid
            break
    if not admin_role_id and role_map:
        admin_role_id = list(role_map.values())[0][0]

    if admin_role_id:
        await conn.execute(
            "INSERT INTO user_roles (id, user_id, role_id, granted_by) VALUES ($1,$2,$3,$4)",
            uuid.uuid4(), admin_id, admin_role_id, admin_id,
        )
        print(f"Assigned admin role to admin@falonilaw.com")

    await conn.close()
    print("Done! Restart dcs-api and re-login to pick up permissions.")


if __name__ == "__main__":
    asyncio.run(setup_roles())
