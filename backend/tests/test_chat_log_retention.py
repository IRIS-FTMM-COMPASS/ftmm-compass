"""Chat log retention when an account is deleted."""

import uuid

from models import ChatLog, User


def test_deleting_user_keeps_chat_log_with_null_author(client, db_session):
    async def run():
        user = User(
            email=f"retention-{uuid.uuid4()}@example.test",
            full_name="Retention Test",
            role="student",
        )
        db_session.add(user)
        await db_session.flush()

        log = ChatLog(
            session_id=f"retention-{uuid.uuid4()}",
            user_id=user.user_id,
            user_message="pesan uji retensi",
        )
        db_session.add(log)
        await db_session.flush()
        log_id = log.id

        await db_session.delete(user)
        await db_session.flush()
        db_session.expire_all()

        retained = await db_session.get(ChatLog, log_id)
        assert retained is not None
        assert retained.user_id is None
        assert retained.user_message == "pesan uji retensi"

    client.portal.call(run)
