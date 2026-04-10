import pytest

from messaging_sdk.services.chat_service import MessageService


@pytest.mark.asyncio
async def test_direct_conversation_and_message_lifecycle(
    db_session,
    user_factory,
    accepted_contact_factory,
):
    service = MessageService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")
    await accepted_contact_factory(alice, bob)

    conversation = await service.create_conversation(alice.id, bob.id)
    message = await service.send_message(conversation.id, alice.id, "hello world")
    edited = await service.edit_message(message.id, alice.id, "updated text")
    marked_read = await service.mark_messages_as_read(conversation.id, bob.id, message.id)
    deleted = await service.delete_message(message.id, alice.id)
    messages = await service.get_messages(conversation.id, bob.id)

    assert conversation.is_group is False
    assert edited.is_edited is True
    assert marked_read is True
    assert deleted.is_deleted is True
    assert messages == []


@pytest.mark.asyncio
async def test_group_admin_only_member_addition(db_session, user_factory):
    service = MessageService(db_session)
    creator = await user_factory("creator")
    member = await user_factory("member")
    extra = await user_factory("extra")

    conversation = await service.create_group_chat(
        creator_id=creator.id,
        name="Core Team",
        participant_ids=[member.id],
        admin_only_add_members=True,
    )

    with pytest.raises(ValueError, match="Only group admins"):
        await service.add_participants_to_group(conversation.id, member.id, [extra.id])

    updated = await service.add_participants_to_group(conversation.id, creator.id, [extra.id])

    assert len(updated.participants) == 3


@pytest.mark.asyncio
async def test_non_participant_cannot_read_or_send_messages(
    db_session,
    user_factory,
    accepted_contact_factory,
):
    service = MessageService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")
    outsider = await user_factory("outsider")
    await accepted_contact_factory(alice, bob)

    conversation = await service.create_conversation(alice.id, bob.id)

    with pytest.raises(ValueError, match="not a participant"):
        await service.get_messages(conversation.id, outsider.id)

    with pytest.raises(ValueError, match="not a participant"):
        await service.send_message(conversation.id, outsider.id, "let me in")
