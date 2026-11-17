"""Kontrak kepemilikan notifikasi dan cakupan tandai-semua."""

import uuid

from models import UserNotification


def _create_notification(client, db_session, **fields) -> str:
    async def insert():
        notification = UserNotification(**fields)
        db_session.add(notification)
        await db_session.commit()
        return str(notification.notification_id)

    return client.portal.call(insert)


def _user_id(client, headers) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/auth/me", headers=headers).json()["user_id"])


def _is_read(client, db_session, notification_id: str) -> bool:
    async def read():
        return (
            await db_session.get(UserNotification, uuid.UUID(notification_id))
        ).is_read

    return client.portal.call(read)


def test_mark_other_users_notification_returns_404(client, student_headers, admin_headers, db_session):
    foreign_id = _create_notification(
        client,
        db_session,
        user_id=_user_id(client, admin_headers),
        title="Notifikasi admin",
        message="Hanya untuk admin",
        type="info",
    )
    response = client.patch(
        f"/api/v1/notifications/{foreign_id}/read", headers=student_headers
    )
    assert response.status_code == 404
    assert _is_read(client, db_session, foreign_id) is False


def test_mark_all_read_matches_visible_list(client, student_headers, admin_headers, db_session):
    student_id = _user_id(client, student_headers)
    global_id = _create_notification(
        client, db_session, title="Pengumuman", message="Global", type="info"
    )
    personal_id = _create_notification(
        client,
        db_session,
        user_id=student_id,
        title="Pribadi",
        message="Untuk mahasiswa",
        type="info",
    )
    hidden_id = _create_notification(
        client,
        db_session,
        target_role="admin",
        title="Admin only",
        message="Tidak tampil",
        type="info",
    )

    response = client.post("/api/v1/notifications/mark-all-read", headers=student_headers)
    assert response.status_code == 200

    visible = client.get("/api/v1/notifications/me", headers=student_headers).json()
    visible_ids = {item["id"] for item in visible["items"]}
    assert global_id in visible_ids
    assert personal_id in visible_ids
    assert hidden_id not in visible_ids
    assert all(item["is_read"] for item in visible["items"])
    assert _is_read(client, db_session, hidden_id) is False


def test_notifications_list_for_student(client, student_headers):
    response = client.get("/api/v1/notifications/me", headers=student_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["items"], list)


def test_mark_all_notifications_read(client, student_headers):
    client.post("/api/v1/notifications/mark-all-read", headers=student_headers)
    body = client.get("/api/v1/notifications/me", headers=student_headers).json()
    assert all(item["is_read"] for item in body["items"])
