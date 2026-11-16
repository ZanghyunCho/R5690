유지보수통 카운터 체크/초기화 활성화 수정본 (AdjProg Ver.1.0.3)

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
