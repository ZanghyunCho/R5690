"""Patch the uploaded Adjustment Program without executing it or accessing a printer."""
from pathlib import Path
import hashlib
import json
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/adjustment-program'
OUT = ROOT / 'artifacts/maintenance-counter-enabled'
BASE = 0x400000


def build():
    original = (SOURCE / 'AdjProg.exe').read_bytes()
    data = bytearray(original)
    # Preserve type 0x17 and its maintenance-box-specific Check/% fallback.
    edits = [
        (0x4F3421, bytes.fromhex('18'), bytes.fromhex('17'),
         'Include type 0x17 in the count of initializable counters'),
        (0x4F398B, bytes.fromhex('17'), bytes.fromhex('16'),
         'Leave the type 0x17 counter checkbox enabled'),
        (0x4F5545, bytes.fromhex('0f8476010000'), bytes.fromhex('0f8455000000'),
         'Route type 0x17 to the existing requested-value write path instead of skipping'),
    ]
    changes = []
    for address, before, after, reason in edits:
        offset = address - BASE
        assert data[offset:offset+len(before)] == before
        data[offset:offset+len(before)] = after
        changes.append(dict(va=hex(address), file_offset=hex(offset), before=before.hex(),
                            after=after.hex(), reason=reason))
    # The program has additive whole-file integrity checks. Preserve their byte
    # sum using raw section padding, outside virtual .text code/data. No integrity
    # check branch, expected signature, or security/driver code is removed.
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    sections = pe + 24 + struct.unpack_from('<H', data, pe+20)[0]
    assert data[sections:sections+8].rstrip(b'\0') == b'.text'
    virtual_size, rva, raw_size, raw_offset = struct.unpack_from('<4I', data, sections+8)
    padding = raw_offset + virtual_size
    assert raw_size > virtual_size and original[padding] == 0
    balance = sum(original) - sum(data)
    assert 0 <= balance <= 255
    data[padding] = balance
    changes.append(dict(file_offset=hex(padding), before='00', after=f'{balance:02x}',
                        reason='Preserve additive file integrity sum in unused raw .text padding'))
    assert len(data) == len(original) and sum(data) == sum(original)
    # The original model definition, logical target FC, read path, and zero-valued
    # Initialize handler remain intact. The changed near jump must land at 55A0.
    assert data[0x699AD0-BASE:0x699AD0-BASE+0x78] == original[0x699AD0-BASE:0x699AD0-BASE+0x78]
    assert struct.unpack_from('<3I', data, 0x699AD0-BASE) == (8, 0x17, 0xFC)
    assert 0x4F554B + struct.unpack_from('<i', data, 0x4F5547-BASE)[0] == 0x4F55A0
    assert data[0x4F48FC-BASE:0x4F4901-BASE] == original[0x4F48FC-BASE:0x4F4901-BASE]
    expected_offsets = {p['va'] for p in changes if 'va' in p}
    assert len(expected_offsets) == 3
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'AdjProg.exe').write_bytes(data)
    manifest = dict(source_sha256=hashlib.sha256(original).hexdigest(),
                    patched_sha256=hashlib.sha256(data).hexdigest(), size=len(data),
                    original_byte_sum=sum(original), patched_byte_sum=sum(data),
                    modified_byte_count=sum(a != b for a, b in zip(original, data)), changes=changes,
                    target='Maintenance counter: type 0x17 / logical ID 0xFC',
                    verification='Static structure, patch bytes, branch target and additive checksum preservation; no Windows/printer execution',
                    limits=['Initializes the program logical EEPROM counter 0xFC; a maintenance-box chip reset is not established',
                            'Does not repair ink-pack recognition, initial-charge or IES conditions'])
    (OUT / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    readme = '''유지보수통 카운터 체크/초기화 활성화 수정본 (AdjProg Ver.1.0.3)

압축을 새 폴더에 풀고 AdjProg.exe를 실행하십시오.
Maintenance counter에서 Maintenance Box counter를 체크한 뒤 Check로 값을 확인하고,
초기화를 원할 때 Initialize를 누르십시오. 기존 확인 창은 유지됩니다.

변경: 읽기 전용 유형 0x17의 체크박스 잠금, Initialize 비활성화 조건,
초기화 처리의 쓰기 제외 조건을 수정했습니다. 기존 Check/잔량 표시 경로는 보존했습니다.
Initialize는 기존 논리 항목 0xFC(EEPROM 0x28–0x29)에 0을 쓰는 경로입니다.
외부 유지보수통 칩 자체를 리셋한다는 뜻은 아닙니다.
Windows 실행과 실제 프린터 초기화는 검증하지 못했습니다.
잉크팩 인식 오류/Initial Charge/IES 상태는 변경하지 않습니다.
원본 실행 파일은 별도로 보관하십시오.
'''
    (OUT / 'README_KO.txt').write_text(readme, encoding='utf-8-sig')
    archive = OUT / 'AdjProg_1.0.3_Maintenance_Counter_Enabled.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(SOURCE.iterdir()):
            z.write(OUT/'AdjProg.exe' if f.name == 'AdjProg.exe' else f, f.name)
        for name in ['MANIFEST.json', 'README_KO.txt']:
            z.write(OUT/name, name)
    print(json.dumps(manifest, indent=2))
    print(archive)


if __name__ == '__main__':
    build()
