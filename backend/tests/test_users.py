from __future__ import annotations

from tests.conftest import login


async def test_list_users_requires_admin(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    token = await login(client, "viewer", "password123")
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_admin_can_list_users(client):
    token = await login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(u["username"] == "admin" for u in resp.json())


async def test_admin_change_role(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "promoted", "password": "password123"}
    )
    admin_token = await login(client, "admin", "admin1234")

    users = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    target = next(u for u in users.json() if u["username"] == "promoted")

    resp = await client.patch(
        f"/api/v1/users/{target['id']}/role",
        json={"role": "analyst"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "analyst"


async def test_admin_delete_user(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "todelete", "password": "password123"}
    )
    admin_token = await login(client, "admin", "admin1234")
    users = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    target = next(u for u in users.json() if u["username"] == "todelete")

    resp = await client.delete(
        f"/api/v1/users/{target['id']}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 204


async def test_register_ignores_any_role(client):
    """Публічна реєстрація не приймає роль узагалі — жодна.

    Раніше `validate_role` перевіряв лише «роль є у списку», тому запит з
    `role: "admin"` проходив і створював адміністратора. Тепер у схемі
    немає поля role, а маршрут бере ROLE_USER з константи, тож значення з
    тіла запиту немає як дістатися до колонки.

    Перевіряємо на всіх ролях і навіть на смітті: відповідь однакова.
    """
    for username, payload_role in (
        ("plaine", None),
        ("wannabe_admin", "admin"),
        ("wannabe_analyst", "analyst"),
        ("nonsense", "superuser"),
    ):
        body = {"username": username, "password": "password123"}
        if payload_role is not None:
            body["role"] = payload_role
        resp = await client.post("/api/v1/auth/register", json=body)
        assert resp.status_code == 201, resp.text
        assert resp.json()["role"] == "user", f"{username} отримав {resp.json()['role']}"


async def test_register_cannot_grant_admin_endpoints(client):
    """Ескалація не проходить не тільки в полі role, а й на рівні доступу.

    Навіть якби роль somehow опинилась admin, require_admin має відкидати
    запит — це друга половина захисту, про яку тести мовчали.
    """
    await client.post(
        "/api/v1/auth/register",
        json={"username": "esc2", "password": "password123", "role": "admin"},
    )
    token = await login(client, "esc2", "password123")
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403
    # і не може підняти собі роль через адмінський ендпойнт
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    resp = await client.patch(
        f"/api/v1/users/{me['id']}/role", json={"role": "admin"}, headers=headers
    )
    assert resp.status_code == 403
