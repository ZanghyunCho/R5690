"""Colour LZ/adaptive-Huffman encoder with original ARM table builder/decoder.

This codec is independent of the outer, hardware-assisted CROM codec.
"""
from pathlib import Path
import struct
from collections import defaultdict
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT = Path(__file__).resolve().parents[1]

class Codec:
    def __init__(self):
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        code = (ROOT/'artifacts/maintenance-virtualization/decoded/107423412.crom.0.bin').read_bytes()
        self.cpu.mem_map(0x4848f000, (len(code)+4095)//4096*4096)
        self.cpu.mem_write(0x4848f000, code)
        self.cpu.mem_map(0x20000000, 0x200000)
        self.cpu.mem_map(0x21000000, 0x20000)
        self.cpu.mem_map(0x22000000, 0x800000)
        self.cpu.mem_map(0x23000000, 0x100000)

    def call(self, address, args, *, instruction_limit=100000000):
        for reg, value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):
            self.cpu.reg_write(reg, value)
        self.cpu.reg_write(UC_ARM_REG_SP, 0x201ff000)
        self.cpu.reg_write(UC_ARM_REG_LR, 0x20000100)
        self.cpu.emu_start(address, 0x20000100, count=instruction_limit)
        assert self.cpu.reg_read(UC_ARM_REG_PC) == 0x20000100
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def decode(self, stream, size):
        # Input starts at 0x20001000 and must not reach the stack at
        # 0x201ff000. This is an emulator mapping bound, not a format limit.
        assert len(stream)<0x1ed000 and size<=0x800000
        self.cpu.mem_write(0x20001000, stream)
        self.cpu.mem_write(0x201ff000, struct.pack('<I',0x21000000))
        assert self.call(0x48ad4b04,[0x20001000,len(stream),0x22000000,size],instruction_limit=max(100000000,size*512)) == size
        return bytes(self.cpu.mem_read(0x22000000,size))

    def transform(self, blob):
        """Run original BA transform, mocking only allocation and release."""
        def memory_helper(cpu, address, size, context):
            if address==0x48aab300:
                assert cpu.reg_read(UC_ARM_REG_R1)<=0x100000
                cpu.reg_write(UC_ARM_REG_R0,0x23000000)
            elif address==0x48aab3e0:
                cpu.reg_write(UC_ARM_REG_R0,0)
            else:
                return
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        handle=self.cpu.hook_add(UC_HOOK_CODE,memory_helper)
        try:
            self.cpu.mem_write(0x22000000,blob)
            assert self.call(0x48abf900,[0x22000000,len(blob),1])==0
            return bytes(self.cpu.mem_read(0x22000000,len(blob)))
        finally:
            self.cpu.hook_del(handle)

    def table(self, frequencies):
        self.cpu.mem_write(0x21004620,struct.pack('<392I',*frequencies))
        self.call(0x48ad478c,[392,0x21000000])
        lookup = struct.unpack('<4096I',self.cpu.mem_read(0x21000000,16384))
        widths = struct.unpack('<392I',self.cpu.mem_read(0x21004000,392*4))
        codes = {}
        for prefix, symbol in enumerate(lookup):
            if symbol not in codes:
                width = widths[symbol]
                assert 1<=width<=12
                codes[symbol]=(prefix>>(12-width),width)
        assert len(codes)==392
        return codes

    def encode(self, data):
        frequencies=[1]*392
        codes=self.table(frequencies)
        counter=3000
        output=bytearray(struct.pack('<I',len(data)))
        bits=buffer=0
        def emit(value,width):
            nonlocal bits,buffer
            assert width>=0 and 0<=value<(1<<width)
            bits+=width;buffer=(buffer<<width)|value
            while bits>=8:
                bits-=8;output.append((buffer>>bits)&255)
            buffer&=(1<<bits)-1
        def symbol(value):
            nonlocal frequencies,codes,counter
            emit(*codes[value])
            frequencies[value]+=1;counter+=1
            if counter==4096:
                codes=self.table(frequencies)
                frequencies=[1]*392;counter=392
        positions=defaultdict(list)
        pos=0;previous_distance=previous_length=1
        while pos<len(data):
            key=data[pos:pos+3]
            best=0;distance=0
            if len(key)==3:
                for candidate in reversed(positions[key][-96:]):
                    dist=pos-candidate
                    if dist>=16384:break
                    length=3
                    while length<min(257,len(data)-pos) and data[candidate+length]==data[pos+length]:
                        length+=1
                    if length>best:
                        best,distance=length,dist
                        if length==257:break
            if best>=3:
                length=best-2
                dc=0 if distance==previous_distance else distance.bit_length()
                lc=0 if length==previous_length else length.bit_length()
                symbol(257+dc*9+lc)
                if dc:emit(distance-(1<<(dc-1)),dc-1)
                if lc:emit(length-(1<<(lc-1)),lc-1)
                previous_distance,previous_length=distance,length
                n=best
            else:
                symbol(data[pos]);n=1
            for p in range(pos,pos+n):
                positions[data[p:p+3]].append(p)
            pos+=n
        if bits:output.append(buffer<<(8-bits))
        # Decoder uses a twelve-bit lookahead, including the final symbol.
        output.extend(b'\0\0')
        stream=bytes(output)
        assert self.decode(stream,len(data)) == data
        return stream
