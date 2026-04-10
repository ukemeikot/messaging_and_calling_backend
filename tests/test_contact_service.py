import pytest

from messaging_sdk.services.contact_service import ContactService


@pytest.mark.asyncio
async def test_send_accept_and_block_contact_flow(
    db_session,
    user_factory,
):
    service = ContactService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")

    request = await service.send_contact_request(alice.id, bob.id)
    assert request.status.value == "pending"

    accepted = await service.accept_contact_request(bob.id, request.id)
    contacts = await service.get_contacts(alice.id)

    assert accepted.status.value == "accepted"
    assert len(contacts) == 1

    await service.block_user(alice.id, bob.id)

    assert await service.is_blocked(alice.id, bob.id) is True


@pytest.mark.asyncio
async def test_duplicate_contact_request_is_rejected(db_session, user_factory):
    service = ContactService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")

    await service.send_contact_request(alice.id, bob.id)

    with pytest.raises(ValueError, match="already sent"):
        await service.send_contact_request(alice.id, bob.id)
