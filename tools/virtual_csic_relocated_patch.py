"""Relocate virtual CSIC helpers out of the stock LCD framebuffer.

Reclaims only retired chip-auth/compatibility bodies, preserves external literal
references and their public entry hooks. No printer or complete boot emulation.
"""
import hashlib,json,struct
from pathlib import Path
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from prototype_virtual_csic_transport import ROOT,BASE,branch
from prototype_virtual_csic_bootstrap import SKUS,TEMPLATES,UIDS,SEED,IS_READY,UID_CACHE,PROPERTY_READY
from virtual_csic_patch import patch as previous_patch

ARENAS=[(0x47c57a04,0x47c5824c),(0x47c8d8d8,0x47c8da00)]
ENTRIES={0x47c57a04,0x47c57e4c,0x47c8d8d8}
FRAMEBUFFER=(0x47d69594,0x47de8d94)

def patch(stock):
    previous,layout=previous_patch(stock)
    image=bytearray(previous);ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
    inside=lambda a:any(lo<=a<hi for lo,hi in ARENAS)
    protected=set()
    for a in ENTRIES:protected.update(range(a,a+4))
    external_branches=[]
    # All branch instructions in the stock ARM text. Retired bodies may call
    # one another, but no live external branch may enter their interiors.
    for off in range(0,0x47d28000-BASE,4):
        a=BASE+off;w=struct.unpack_from('<I',stock,off)[0]
        if inside(a):continue
        if w&0x0e000000==0x0a000000:
            d=w&0xffffff
            if d&0x800000:d-=0x1000000
            target=a+8+d*4
            if inside(target) and target not in ENTRIES:external_branches.append([hex(a),hex(target)])
        # Preserve outside PC-relative literal references, including nearby
        # shared pools. Reserve eight bytes conservatively.
        if w&0x0f3f0000==0x051f0000:
            target=a+8+(w&0xfff)*(1 if w&(1<<23) else -1)
            if inside(target):protected.update(range(target&~3,(target&~3)+8))
    assert not external_branches,external_branches
    # Preserve absolute data/function pointers from every relevant module.
    for filename in ['119075160.crom.0.bin','107423412.crom.0.bin','114880856.crom.1.bin',
                     '119075160.crom.1.bin','119075160.crom.2.bin']:
        data=(ROOT/'artifacts/maintenance-virtualization/decoded'/filename).read_bytes()
        for off in range(0,len(data)-3,4):
            if filename=='119075160.crom.0.bin' and inside(BASE+off):continue
            target=struct.unpack_from('<I',data,off)[0]
            if inside(target&~1) and target not in ENTRIES:protected.update(range(target&~3,(target&~3)+8))
    occupied=set(protected);allocations=[]
    def allocate(size,label):
        size=(size+3)&~3
        for lo,hi in ARENAS:
            for a in range(lo,hi-size+1,4):
                if not any(v in occupied for v in range(a,a+size)):
                    occupied.update(range(a,a+size));allocations.append(dict(label=label,start=hex(a),bytes=size))
                    return a
        raise AssertionError(('Retired code arena exhausted',label,size))
    def put(a,b):image[a-BASE:a-BASE+len(b)]=b
    def asm(text,a):return bytes(ks.asm(text,addr=a)[0])
    rows=json.loads((ROOT/'artifacts/virtual-csic-images/REPORT.json').read_text())['cases']
    assert len(rows)==24 and all(r['native_capacity_scale'] in [1,5] and r['kind']==12 for r in rows)
    skus=list(dict.fromkeys(int(r['sku'],16) for r in rows))
    sku_addr=allocate(6,'SKU identifiers');put(sku_addr,bytes(skus))
    part_data=b''.join(struct.pack('<HH',int(r['part_code'],16),r['raw_capacity'] | (0x8000 if r['native_capacity_scale']==5 else 0)) for r in rows)
    part_addr=allocate(len(part_data),'compact part/capacity table');put(part_addr,part_data)
    uid_data=previous[UIDS-BASE:UIDS-BASE+88]
    uid_addr=allocate(88,'stable virtual UIDs');put(uid_addr,uid_data)
    fixed=[(0x57,1),(0x59,12),(0x48,0x3f),(0x49,0xf),(0x4a,0x1f),(0x79,0x40)]
    fixed_addr=allocate(len(fixed)*4,'fixed metadata fields');put(fixed_addr,b''.join(struct.pack('<HH',*r) for r in fixed))
    chunks=[(int(a,16),int(b,16)-int(a,16)) for a,b in layout['cave_spans']
            if int(a,16) not in [SKUS,TEMPLATES,UIDS,SEED]]
    chunks +=[(int(r['helper'],16),r['bytes']) for r in layout['virtual_acceptance_adapters'] if 'helper' in r]
    chunks=sorted(set(chunks))
    destinations={a:allocate(n,'helper from '+hex(a)) for a,n in sorted(chunks,key=lambda r:-r[1])}
    seed_addr=allocate(400,'compact metadata bootstrap')
    translation={**destinations,SEED:seed_addr,UIDS:uid_addr,SKUS:sku_addr}
    ready_addr=destinations[IS_READY];clean_addr=destinations[0x47d70600]
    seed=asm(f'''push {{r1-r9,lr}}
        sub sp,sp,#8
        mov r4,r0
        bl {ready_addr}
        cmp r0,#0
        beq ready
        ldr r6,={PROPERTY_READY}
        ldr r6,[r6]
        cmp r6,#0
        moveq r0,#2
        beq exit
        ldr r0,=0x2e6
        mov r1,sp
        mov r2,#1
        bl 0x47c4b0c8
        ldrb r6,[sp]
        ldr r7,={sku_addr}
        mov r8,#0
    search:
        ldrb r9,[r7,r8]
        cmp r6,r9
        beq found
        add r8,r8,#1
        cmp r8,#6
        blo search
        mov r0,#1
        b exit
    found:
        add r8,r4,r8,lsl #2
        ldr r7,={part_addr}
        add r7,r7,r8,lsl #2
        ldrh r8,[r7]
        ldrh r9,[r7,#2]
        mov r0,r4
        bl 0x47c51b4c
        bl 0x47c51a60
        mov r1,#0
        mov r2,#84
    zero_bank:
        strh r1,[r0],#2
        subs r2,r2,#1
        bne zero_bank
        ldr r7,={fixed_addr}
        mov r6,#6
    fixed_fields:
        mov r0,r4
        ldrh r1,[r7],#2
        ldrh r2,[r7],#2
        bl 0x47c52674
        subs r6,r6,#1
        bne fixed_fields
        mov r0,r4
        mov r1,#0x52
        bic r2,r9,#0x8000
        bl 0x47c52674
        mov r0,r4
        mov r1,#0x53
        mov r2,r8
        bl 0x47c52674
        mov r0,r4
        mov r1,#0x57
        mov r2,r9,lsr #15
        bl 0x47c52674
        mov r0,r4
        mov r1,#0x72
        add r2,r4,#0x40
        bl 0x47c52674
        mov r0,r4
        bl {clean_addr}
        mov r6,#22
        mul r6,r4,r6
        ldr r7,={uid_addr}
        add r7,r7,r6
        ldr r8,={UID_CACHE}
        add r8,r8,r6
        mov r6,#22
    copy_uid:
        ldrb r9,[r7],#1
        strb r9,[r8],#1
        subs r6,r6,#1
        bne copy_uid
    ready:
        mov r0,#0
    exit:
        add sp,sp,#8
        pop {{r1-r9,pc}}
    ''',seed_addr)
    assert len(seed)<=400,len(seed);put(seed_addr,seed)
    # Relocate ARM branches and absolute literal words. PC-relative literal
    # offsets within a chunk stay unchanged under relocation.
    changed_fallbacks=[]
    for old,n in chunks:
        blob=bytearray(previous[old-BASE:old-BASE+n]);new=destinations[old]
        for entry,status in [(0x47c57e4c,0),(0x47c57a04,1),(0x47c8d8d8,1)]:
            record=next(r for r in layout['virtual_acceptance_adapters'] if int(r['entry'],16)==entry)
            if int(record['helper'],16)!=old:continue
            for i in range(4,n,4):
                w=struct.unpack_from('<I',blob,i)[0]
                if w==branch(old+i,entry+4):
                    assert struct.unpack_from('<I',blob,i-4)[0]==struct.unpack_from('<I',stock,entry-BASE)[0]
                    struct.pack_into('<II',blob,i-4,0xe3a00000|status,0xe12fff1e)
                    changed_fallbacks.append(hex(entry));break
            else:raise AssertionError(('Missing retired fallback',hex(entry)))
        for i in range(0,n,4):
            w=struct.unpack_from('<I',blob,i)[0]
            if w in translation:struct.pack_into('<I',blob,i,translation[w]);continue
            if w&0x0e000000==0x0a000000:
                d=w&0xffffff
                if d&0x800000:d-=0x1000000
                target=old+i+8+d*4
                if old<=target<old+n:target=new+target-old
                else:target=translation.get(target,target)
                delta=target-(new+i)-8;assert delta%4==0 and -(1<<25)<=delta<(1<<25)
                struct.pack_into('<I',blob,i,(w&0xff000000)|((delta//4)&0xffffff))
        put(new,blob)
    # Update every entry branch into a relocated helper.
    hooks=[]
    for off in range(0,0x47d28000-BASE,4):
        a=BASE+off;w=struct.unpack_from('<I',previous,off)[0]
        if w&0x0e000000!=0x0a000000:continue
        d=w&0xffffff
        if d&0x800000:d-=0x1000000
        target=a+8+d*4
        if target in destinations:
            assert a not in [x for x,_ in chunks]
            put(a,struct.pack('<I',(w&0xff000000)|((destinations[target]-a-8)//4&0xffffff)))
            hooks.append(dict(entry=hex(a),helper=hex(destinations[target])))
    # Erase all injected framebuffer content by restoring original bytes.
    lo,hi=FRAMEBUFFER;end=min(hi,BASE+len(stock));put(lo,stock[lo-BASE:end-BASE])
    for a in protected:
        if a not in {v for entry in ENTRIES for v in range(entry,entry+4)} and inside(a):
            assert image[a-BASE]==stock[a-BASE],hex(a)
    assert image[lo-BASE:end-BASE]==stock[lo-BASE:end-BASE]
    # There must be no branch/literal to the old framebuffer helper area in
    # any newly allocated chunk. Entries remain outside the framebuffer.
    for allocation in allocations:
        a=int(allocation['start'],16);assert not(lo<=a<hi)
        if allocation['label'].startswith('helper') or allocation['label']=='compact metadata bootstrap':
            for off in range(0,allocation['bytes'],4):
                w=struct.unpack_from('<I',image,a-BASE+off)[0]
                assert not(lo<=w<hi),('Framebuffer literal in helper',hex(a+off),hex(w))
                if w&0x0e000000==0x0a000000:
                    delta=w&0xffffff
                    if delta&0x800000:delta-=0x1000000
                    target=a+off+8+delta*4
                    assert not(lo<=target<hi),('Framebuffer branch in helper',hex(a+off),hex(target))
    layout=dict(controller_sha256=hashlib.sha256(image).hexdigest(),allocations=allocations,
        retired_auth_code_ranges=[[hex(a),hex(b)] for a,b in ARENAS],protected_literal_bytes=len(protected),
        external_interior_branches=external_branches,retired_invalid_input_fallbacks=changed_fallbacks,
        entry_hooks=hooks,framebuffer_range=[hex(lo),hex(hi)],framebuffer_bytes_restored_to_stock=True,
        compact_metadata_bytes=len(part_data)+len(fixed)*4+6+len(uid_data),
        stock_hardware_init_and_gpio_preserved=True,skus=skus,
        limitation='Original display-memory collision removed; physical boot and complete OS still unverified.')
    return bytes(image),layout
