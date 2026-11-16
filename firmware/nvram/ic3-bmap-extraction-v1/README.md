# IC3 BMAP 원본 EEPROM 추출 및 전체 주소 분석

`IC3_BMAP_ACTIVE.eep`는 사용자가 새로 제공한 IC3 덤프의 유효 BMAP 사본에서 추출한 **2,048바이트 원본**입니다. 별도 초기화·Flag 변경·IES 조작은 하지 않았습니다.

- BMAP 구역: `0xFD0000` / `0xFE0000`.
- 유효 상태 `0x3F`인 항목: FD 구역 29번.
- 추출 범위: IC3 파일 `0xFDE830–0xFDF02F`.
- 순정 참조 ARM 선택 루틴 `0x47C957EC`을 제한 실행해 29번 선택과 대조했습니다. 실제 장치 부팅·flash 읽기는 시험하지 않았습니다.
- 이 사본의 초기 충전 Flag와 청소 예약 Flag는 모두 0입니다. 앞선 청소 Flag 해제로도 증상이 바뀌지 않았다는 사용자 보고가 있으므로, 같은 비트를 다시 지우는 수정 파일은 만들지 않았습니다.
- 이전 서비스 EEPROM 백업과는 242바이트 다르며, 실제 채취 시점의 선후 관계는 미확인입니다. 이 추출을 최신 상태 복원용이나 오류 해결 파일로 보장하지 않습니다.

전체 설명은 [IC3_NVRAM_REPORT_KO.md](IC3_NVRAM_REPORT_KO.md), 한 번에 받는 파일은 [IC3_NVRAM_ANALYSIS_AND_EEP.zip](IC3_NVRAM_ANALYSIS_AND_EEP.zip)입니다. 보고서는 IC3의 0–F 주소 범위, sector 145개, BMAP 사본, EEPROM 2,048바이트 전체를 다룹니다. 확인되지 않은 필드의 의미는 미확인으로 표시했습니다.

추가로 확인한 조정 기능명·상태 항목 대응은 [논리 ID별 기능 대응표](../logical-address-map-v1/LOGICAL_ADDRESS_MEANINGS_KO.md)에 정리했습니다. 여기에는 `0x261`의 잉크 누수 오류 리셋 대상, Bi-D/PF/PW 보정, BAM 옵션, 유지보수통 카운터 등 모델 설정표와 연결한 근거가 포함됩니다.

이 파일은 IC3 전체 이미지나 EFU가 아닙니다. EEPROM 논리 주소와 IC3의 물리 오프셋은 서로 다릅니다. IES 관련 저장 항목과 설치 오류 원인은 아직 특정하지 못했습니다.
