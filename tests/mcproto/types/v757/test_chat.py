from __future__ import annotations

import pytest

from mcproto.buffer import Buffer
from mcproto.types.v757.chat import ChatMessage, RawChatMessage


@pytest.mark.parametrize(
    ("data", "expected_bytes"),
    [
        (
            "A Minecraft Server",
            bytearray.fromhex("142241204d696e6563726166742053657276657222"),
        ),
        (
            {"text": "abc"},
            bytearray.fromhex("0f7b2274657874223a2022616263227d"),
        ),
        (
            [{"text": "abc"}, {"text": "def"}],
            bytearray.fromhex("225b7b2274657874223a2022616263227d2c207b2274657874223a2022646566227d5d"),
        ),
    ],
)
def test_serialize(data: RawChatMessage, expected_bytes: list[int]):
    output_bytes = ChatMessage(data).serialize()
    assert output_bytes == expected_bytes


@pytest.mark.parametrize(
    ("input_bytes", "data"),
    [
        (
            bytearray.fromhex("142241204d696e6563726166742053657276657222"),
            "A Minecraft Server",
        ),
        (
            bytearray.fromhex("0f7b2274657874223a2022616263227d"),
            {"text": "abc"},
        ),
        (
            bytearray.fromhex("225b7b2274657874223a2022616263227d2c207b2274657874223a2022646566227d5d"),
            [{"text": "abc"}, {"text": "def"}],
        ),
    ],
)
def test_deserialize(input_bytes: list[int], data: RawChatMessage):
    chat = ChatMessage.deserialize(Buffer(input_bytes))
    assert chat.raw == data
