"""Modify the uploaded updater's downgrade policy; never execute it or flash a printer."""
from pathlib import Path
import hashlib
import json
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/workspace/attachments/a9414c97-9034-4232-a988-6c18ea14dce1/EPFWUPD.exe')
OUT = ROOT / 'artifacts/updater-downgrade-allowed-v1'
SOURCE_HASH = 'a200845cb97241382c7c8593f173a78dc3b4760a9088711e9b329cc14e808aa5'


def pe_checksum(data, checksum_offset):
    total = 0
    for off in range(0, len(data), 2):
        if checksum_offset <= off < checksum_offset+4:
            continue
        total += int.from_bytes(data[off:off+2], 'little')
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return total + len(data)


def build():
    original = SOURCE.read_bytes()
    assert hashlib.sha256(original).hexdigest() == SOURCE_HASH
    data = bytearray(original)
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    opt = pe+24
    assert struct.unpack_from('<H', data, opt)[0] == 0x10B
    assert struct.unpack_from('<I', data, opt+28)[0] == 0x400000
    section_table = opt+struct.unpack_from('<H', data, pe+20)[0]
    sections = []
    for i in range(struct.unpack_from('<H', data, pe+6)[0]):
        o = section_table+40*i
        vs, rva, rs, raw = struct.unpack_from('<4I', data, o+8)
        sections.append((rva, rs, raw))

    def offset(va):
        for rva, size, raw in sections:
            if rva <= va-0x400000 < rva+size:
                return raw+va-0x400000-rva
        raise ValueError(hex(va))

    # Both concrete policy vtables use the same +0x84 accessor.
    for vtable in (0x66E6B4, 0x66EF7C):
        assert struct.unpack_from('<I', data, offset(vtable+0x84))[0] == 0x4507CC
    site = offset(0x4507D8)
    before = bytes.fromhex('80790500')
    after = bytes.fromhex('eb0a9090')
    assert data[site:site+4] == before
    assert data[offset(0x4507E4):offset(0x4507E4)+4] == bytes.fromhex('b001eb49')
    data[site:site+4] = after
    assert 0x4507D8+2+data[site+1] == 0x4507E4
    assert 0x4507E6+2+data[offset(0x4507E6)+1] == 0x450831
    # Preserve the entry/SEH frame and original cleanup/return path.
    assert data[offset(0x4507CC):site] == original[offset(0x4507CC):site]
    assert data[offset(0x450831):offset(0x450837)] == original[offset(0x450831):offset(0x450837)]

    # Editing invalidates the vendor signature. Remove its now-invalid directory
    # and certificate overlay, rather than presenting it as a valid signed file.
    security_offset = opt+96+8*4
    cert_offset, cert_size = struct.unpack_from('<II', data, security_offset)
    raw_end = max(raw+size for _, size, raw in sections)
    assert cert_offset == raw_end and cert_offset+cert_size == len(data)
    del data[cert_offset:]
    struct.pack_into('<II', data, security_offset, 0, 0)
    checksum_offset = opt+64
    struct.pack_into('<I', data, checksum_offset, 0)
    checksum = pe_checksum(data, checksum_offset)
    struct.pack_into('<I', data, checksum_offset, checksum)
    assert pe_checksum(data, checksum_offset) == checksum
    allowed = set(range(site, site+4)) | set(range(security_offset, security_offset+8)) | set(range(checksum_offset, checksum_offset+4))
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(original, data)))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'EPFWUPD.exe').write_bytes(data)
    manifest = dict(source_sha256=SOURCE_HASH, patched_sha256=hashlib.sha256(data).hexdigest(),
                    source_bytes=len(original), patched_bytes=len(data),
                    patch=dict(va='0x4507D8', file_offset=hex(site), before=before.hex(), after=after.hex(),
                               effect='Common downgrade permission accessor returns AL=1 through its existing cleanup'),
                    policy_vtable_slots=['0x66E738', '0x66F000'],
                    integrity=dict(pe_checksum=hex(checksum), vendor_signature='removed; modified executable is unsigned',
                                   removed_certificate_bytes=cert_size),
                    verification='Source SHA-256, both vtables, branch targets, preserved prologue/epilogue, complete byte diff, PE checksum and archive consistency; no Windows or printer execution',
                    limits=['Host-side downgrade policy only; printer-side rejection is not bypassed',
                            'No EFU/model/USB/firmware payload changes',
                            'No device update tested'])
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (OUT/'README_KO.txt').write_text('''EPFWUPD — PC 측 다운그레이드 허용 수정본 v1

업데이터를 종료하고 기존 EPFWUPD.exe를 별도 보관하십시오.
이 ZIP의 EPFWUPD.exe를 기존 업데이터 폴더에 넣어 실행하십시오.
기존의 다른 파일과 EFU는 그대로 필요합니다.
프린터 선택 화면에서 새로 고침한 뒤 프린터를 선택하십시오.

변경: 다운그레이드 허용 정책 함수가 허용을 반환하도록 수정했습니다.
문구만 바꾸는 수정이 아닙니다. 원래 버전 비교와 모델/통신 검사는 유지됩니다.
공급업체 서명은 수정 후 유효하지 않으므로 제거했으며, 이 파일은 서명되지 않았습니다.
PE 체크섬을 다시 계산했습니다.

Windows 실행 및 실제 업데이트는 미검증입니다.
프린터 자체가 다운그레이드를 거부하면 이 수정만으로 해결되지 않습니다.
EFU 자체와 잉크팩 인식/충전 오류는 변경하지 않습니다.
''', encoding='utf-8-sig')
    archive = OUT/'EPFWUPD_Downgrade_Allowed_v1.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ['EPFWUPD.exe', 'README_KO.txt', 'MANIFEST.json']:
            z.write(OUT/name, name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and z.read('EPFWUPD.exe') == data
    print(json.dumps(manifest, indent=2))
    print(archive)


if __name__ == '__main__':
    build()
