import pytest
from fastapi import HTTPException

from messaging_sdk.services.call_service import CallService


@pytest.mark.asyncio
async def test_call_lifecycle(db_session, user_factory):
    service = CallService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")

    call = await service.initiate_call(alice.id, [bob.id], "audio")
    answered = await service.answer_call(call.id, bob.id)

    assert call.call_mode == "1-on-1"
    assert answered.status == "active"

    ended = await service.end_call(call.id, bob.id)
    assert ended.status == "ended"


@pytest.mark.asyncio
async def test_group_call_invites_add_new_participant(db_session, user_factory):
    service = CallService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")
    charlie = await user_factory("charlie")
    dora = await user_factory("dora")

    call = await service.initiate_call(alice.id, [bob.id, charlie.id], "video", max_participants=4)
    await service.answer_call(call.id, bob.id)

    invited_participants = await service.invite_to_call(call.id, alice.id, [dora.id])
    active_calls = await service.get_active_calls(bob.id)

    assert len(invited_participants) == 1
    assert invited_participants[0].user_id == dora.id
    assert len(active_calls) == 1


@pytest.mark.asyncio
async def test_validate_signaling_access_rejects_non_participants(db_session, user_factory):
    service = CallService(db_session)
    alice = await user_factory("alice")
    bob = await user_factory("bob")
    outsider = await user_factory("outsider")

    call = await service.initiate_call(alice.id, [bob.id], "audio")

    with pytest.raises(HTTPException) as outsider_exc:
        await service.validate_signaling_access(call.id, outsider.id)

    with pytest.raises(HTTPException) as target_exc:
        await service.validate_signaling_access(call.id, alice.id, outsider.id)

    assert outsider_exc.value.status_code == 403
    assert target_exc.value.status_code == 403
