"""Response tagging preserves packet content and does not mutate the source packet."""

from nortpole.chat.emitter import Emitter
from nortpole.server.query_and_chat.placement import Placement
from nortpole.server.query_and_chat.streaming_models import OverallStop, Packet


def test_emitter_tags_model_without_changing_source_packet() -> None:
    delivered: list[Packet] = []
    emitter = Emitter(delivered.append, model_idx=2)
    packet = Packet(
        placement=Placement(turn_index=5, tab_index=3, sub_turn_index=2),
        obj=OverallStop(stop_reason="test"),
    )
    original = packet.model_copy(deep=True)

    emitter.emit(packet)

    assert packet == original
    assert delivered == [
        packet.model_copy(
            update={"placement": packet.placement.model_copy(update={"model_index": 2})}
        )
    ]
