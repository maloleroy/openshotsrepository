import hashlib,struct
import pytest
from openshots.binary import encode_blocks,decode_block,normalize
@pytest.mark.parametrize('width',[1,7,8,9,49,64,100,255,256])
def test_exact_round_trip(width):
    entries=[(0,1),(2**width-1,2**32-1)]
    payload=next(encode_blocks(entries,width))
    assert list(decode_block(payload,width=width,checksum=hashlib.sha256(payload).hexdigest()))==entries

def test_chunk_boundaries():
    blocks=list(encode_blocks(((i,1) for i in range(65537)),17))
    assert len(blocks)==2
    assert len(list(decode_block(blocks[0],width=17)))==65536
    assert list(decode_block(blocks[1],width=17))==[(65536,1)]

def test_corruption():
    payload=next(encode_blocks([(0,1)],3))
    for bad in [payload[:-1],b'BAD!'+payload[4:],payload[:16]+b'\x80'+payload[17:]]:
        with pytest.raises(ValueError): list(decode_block(bad,width=3))
    with pytest.raises(ValueError): list(decode_block(payload,width=3,checksum='wrong'))
    with pytest.raises(ValueError): normalize({'01':1,1:2},2)

def test_quasi_weights():
    entries=[(0,-0.2),(1,1.2)]
    payload=next(encode_blocks(entries,1,True))
    assert list(decode_block(payload,width=1,weighted=True))==entries
