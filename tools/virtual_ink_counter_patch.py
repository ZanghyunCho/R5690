"""Ink-use status fix for the virtual CSIC controller (V6/V7 lineage).

Stock status evaluator 0x47C61B24 compares per-colour cumulative ink-use
properties 0x808/0x809/0x80D/0x80E with the cartridge capacity thresholds.
Those counters are only reset when a NEW pack identity is registered
(0x47C58B5C -> 0x47C5BB68(slot, 0)). Virtual identities are stable, so the
counters grow forever: near-end (record 0x83, state 4) and finally ink end
(state 6) would follow even with full, refilled packs.

This patch replaces ONLY the four property reads inside 0x47C61B24 with zero
stores, in place (no code cave). The counters themselves, the accumulator,
virtual chip synchronisation, and the debounced sensor flag 0x47D5EE1C path
(set by 0x47C62038) are unchanged, so a sensor-detected end still produces
the stock end state.
"""
import struct
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM

BASE=0x47c48000
START,END=0x47c61b78,0x47c61bbc
STOCK_WORDS=[0xe59f0618,0xe3a02004,0xe1a0100d,None,0xe59f060c,0xe3a02004,0xe1a0400d,0xe28d1004,None,
             0xe59f05fc,0xe3a02004,0xe2841008,None,0xe59f05f0,0xe3a02004,0xe284100c,None]

def patch(controller):
    image=bytearray(controller)
    words=struct.unpack_from(f'<{(END-START)//4}I',image,START-BASE)
    for got,want in zip(words,STOCK_WORDS):
        if want is None:assert got&0xff000000==0xeb000000
        else:assert got==want,(hex(got),hex(want))
    ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
    code=bytes(ks.asm('''mov r0,#0
        str r0,[sp]
        str r0,[sp,#4]
        str r0,[sp,#8]
        str r0,[sp,#12]
        mov r4,sp''',addr=START)[0])
    code+=struct.pack('<I',0xe1a00000)*((END-START-len(code))//4)
    assert len(code)==END-START
    image[START-BASE:END-BASE]=code
    return bytes(image),dict(function='0x47C61B24',replaced=[hex(START),hex(END)],
        operation='cumulative ink-use reads 0x808/0x809/0x80D/0x80E -> 0 for status evaluation only')
