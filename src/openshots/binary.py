"""OSB1 transport. Bit zero is classical bit zero; strings print MSB first."""
from __future__ import annotations
import hashlib
import math
import struct
from collections.abc import Iterable, Iterator, Mapping

MAX_ENTRIES = 65536
HEADER = struct.Struct('<4sHBBQ')

def state_int(state: str | int, width: int) -> int:
    if not 1 <= width <= 256:
        raise ValueError('measured width must be 1..256')
    if isinstance(state, str):
        state = state.replace(' ', '')
        if len(state) != width or any(c not in '01' for c in state):
            raise ValueError('state must be a fixed-width binary string')
        state = int(state, 2)
    if type(state) is not int or not 0 <= state < 1 << width:
        raise ValueError('state does not fit measured width')
    return state

def normalize(values: Mapping[str | int, int | float], width: int, weighted: bool = False) -> list[tuple[int, int | float]]:
    output = {}
    for key, value in values.items():
        key = state_int(key, width)
        if key in output:
            raise ValueError('duplicate states after normalization')
        output[key] = value
    return sorted(output.items())

def encode_blocks(entries: Iterable[tuple[int, int | float]], width: int, weighted: bool = False) -> Iterator[bytes]:
    state_int(0, width)
    state_bytes = (width + 7) // 8
    payload = bytearray()
    count = 0
    previous = -1
    for state, value in entries:
        state = state_int(state, width)
        if state <= previous:
            raise ValueError('entries must be unique and sorted numerically')
        previous = state
        if weighted:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('weights must be finite numbers')
            encoded = struct.pack('<d', value)
        else:
            if type(value) is not int or not 0 < value <= 0xFFFFFFFF:
                raise ValueError('counts must be positive u32 values')
            encoded = struct.pack('<I', value)
        payload.extend(state.to_bytes(state_bytes, 'little'))
        payload.extend(encoded)
        count += 1
        if count == MAX_ENTRIES:
            yield HEADER.pack(b'OSB1', width, int(weighted), 0, count) + payload
            payload.clear()
            count = 0
    if count:
        yield HEADER.pack(b'OSB1', width, int(weighted), 0, count) + payload

def decode_block(payload: bytes, *, width: int, weighted: bool = False, checksum: str | None = None) -> Iterator[tuple[int, int | float]]:
    if checksum is not None and hashlib.sha256(payload).hexdigest() != checksum:
        raise ValueError('OSB1 checksum mismatch')
    if len(payload) < HEADER.size:
        raise ValueError('truncated OSB1 header')
    magic, actual_width, encoding, reserved, count = HEADER.unpack_from(payload)
    if magic != b'OSB1' or reserved or actual_width != width or encoding != int(weighted) or not 1 <= width <= 256 or not 1 <= count <= MAX_ENTRIES:
        raise ValueError('invalid OSB1 header')
    state_bytes = (width + 7) // 8
    stride = state_bytes + (8 if weighted else 4)
    if len(payload) != HEADER.size + count * stride:
        raise ValueError('incorrect OSB1 length')
    previous = -1
    for offset in range(HEADER.size, len(payload), stride):
        state = int.from_bytes(payload[offset:offset + state_bytes], 'little')
        value = struct.unpack_from('<d' if weighted else '<I', payload, offset + state_bytes)[0]
        if not previous < state < 1 << width or (weighted and not math.isfinite(value)) or (not weighted and value == 0):
            raise ValueError('invalid OSB1 state order, padding or value')
        previous = state
        yield state, value
