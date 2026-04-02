# CLAUDE.md — thin-recon 사전 실험

## 프로젝트 목적

ISPRS 2026 논문의 방법론 방향을 결정하기 위한 사전 실험.

### 배경

드론 이미지에서 전선(power line) 같은 thin structure의 3D reconstruction을 개선하는 연구. MVS가 전선에서 texture matching 실패 → depth map에 빈 구멍. Depth foundation model은 전선 depth를 추정하지만 배경 건물 쪽으로 bias될 수 있음.

해결 방법으로 Prior Depth Anything (MVS sparse metric points + foundation model fusion)을 사용하는데, 전주(pole)는 MVS에서 잘 잡히므로 전주 depth가 Prior DA의 sparse prior에 포함됨. 전주는 전선과 유사한 depth에 위치.

### 핵심 질문

**Foundation model의 relative depth에서, 전선의 depth가 전주에 가까운가, 배경 건물에 가까운가?**

### 판단 기준과 연구 방향

- **전선 ≈ 전주** → **방향 A 채택**: Prior DA에 MVS sparse points (전주 포함)만 넣어도 전주 depth가 전선으로 전파됨. Catenary 같은 도메인 특화 가정 불필요. 더 범용적.
- **전선 ≈ 배경** → **방향 B 채택**: Prior DA가 전선을 배경으로 취급하여 전주 depth가 전파 안 됨. Catenary 물리 모델로 전선 pixel에 직접 metric anchor를 제공해야 함.
- **방향 A가 가능하면 A를 우선 채택** — 추가 가정 없이 thin structure 일반에 적용 가능하므로.

## 현재 상태

- **데이터**: 드론 multi-view 이미지 180장 (DJI 촬영, 8192x5460, 성수동)
- **사전 실험**: 완료. PatchFusion으로 180장 전체 relative depth map 생성 완료
- **사전 실험 결과**: **방향 A 채택** — 전선 depth ≈ 전주 depth (상세: `docs/pilot_experiment_report.md`)
- **SfM/MVS**: 미처리. 본 실험에서 COLMAP으로 진행 예정
- **해상도 문제**: 8192x5460은 depth model에 직접 입력 불가. 다운샘플하면 전선(수 pixel 폭)이 사라짐 → **PatchFusion 사용** (고해상도 패치 기반 depth estimation, CVPR 2024)
- **환경**: 로컬 PC에 NVIDIA RTX 3090 x2, VS Code Remote SSH로 접속, Docker 사용

## 사전 실험 워크플로우

```
Step 1: PatchFusion 환경 구축 + 실행 (Claude Code)
  → 원본 RGB (8192x5460) → 고해상도 relative depth map

Step 2: 이미지 선별 (Claude Code + 사용자)
  → 전주와 전선이 함께 보이는 이미지 2~3장 선택

Step 3: 웹 기반 영역 지정 (Claude Code 구축 + 사용자 클릭)
  → interactive HTML 페이지에서 전주/전선/배경 클릭 → regions.json 저장

Step 4: 분석 (Claude Code)
  → regions.json + depth map → 방향 판정
```

## Step 1: PatchFusion

### Docker 환경

GitHub: https://github.com/zhyever/PatchFusion

### PatchFusion 실행

- PatchFusion repo를 클론하고 Docker 환경에서 실행
- 8192x5460 이미지에 대해 패치 기반 depth estimation
- image_raw_shape, patch_split_num을 이미지 크기에 맞게 설정
- 출력: per-image .npy float32 depth map

주의사항:
- PatchFusion은 DA V1 기반. 의존성이 복잡 (mmengine, mmcv 등)
- repo README를 반드시 확인하고 Dockerfile과 스크립트를 실제 API에 맞게 수정
- VRAM 부족 시 process_num을 줄이거나 mode를 r64 등으로 변경

## Step 2: 이미지 선별

모든 이미지에 전주가 보이지는 않음. 전주와 전선이 **함께 보이는 이미지 2~3장**이면 충분.

Claude Code가:
1. 모든 이미지의 썸네일 생성 (다운샘플)
2. 사용자에게 "전주와 전선이 함께 보이는 이미지를 골라주세요"라고 요청
3. 선택된 이미지에 대해서만 이후 단계 진행

## Step 3: 웹 기반 영역 지정 (핵심)

### 목적

사용자가 VS Code에서 웹 페이지를 열고, 이미지 위에서 클릭하여 전주/전선/배경 영역을 지정. 결과가 regions.json으로 저장됨.

### 구현 요구사항

Claude Code가 다음을 생성해야 함:

**interactive HTML 페이지** (scripts/region_selector/):
- RGB 이미지와 depth map을 나란히 (또는 탭 전환으로) 표시
- 영역 타입 선택 버튼: pole_top / wire_near_pole / wire_center / background / sky
- 이미지 위 클릭 → 해당 좌표에 컬러 마커 표시
- 클릭한 좌표와 영역 타입이 리스트로 누적 표시
- "Save" 버튼 → regions.json 다운로드
- 이미지가 큰 경우 (8192x5460) 줌/팬 기능 필요
- 표시용은 다운샘플 이미지, 좌표는 원본 해상도 기준으로 변환

### 실행 방법

```bash
# 서버에서 HTTP 서버 실행
cd scripts/region_selector
python -m http.server 8000

# VS Code Remote SSH에서 포트 포워딩 자동
# → 브라우저에서 localhost:8000 접속
```

### regions.json 형식

```json
{
  "image": "DJI_xxx.JPG",
  "pole_top": [[3200, 1800], [3210, 1820]],
  "wire_near_pole": [[3400, 1850], [3420, 1860]],
  "wire_center": [[4096, 1900], [4100, 1910]],
  "background": [[3500, 2500], [3600, 2600]],
  "sky": [[4000, 500]]
}
```

## Step 4: 분석

### 실행

```bash
python scripts/analyze_depth.py \
    --rgb data/images/DJI_xxx.JPG \
    --depth data/depth_output/DJI_xxx_depth.npy \
    --regions scripts/region_selector/regions.json \
    --output_dir data/analysis
```

### 핵심 계산

```python
pole_depth = mean(region_pole_top)       # r=1 평균 (pole은 넓으므로 OK)
wire_depth = min_in_neighborhood(region_wire_center)  # 주변 17x17에서 최소값
bg_depth = mean(region_background)       # r=1 평균

ratio = (wire_depth - pole_depth) / (bg_depth - pole_depth)
```

**주의**: 전선은 2~3 pixel 폭이므로 patch 평균(mean)을 쓰면 배경 pixel에 오염된다.
반드시 클릭 주변에서 depth 최소값(= 전선 pixel)을 찾아야 한다.
상세: `docs/pilot_experiment_report.md` "Sampling 문제와 해결" 섹션.

### 판단 기준

| ratio | 판단 | 방향 |
|-------|------|------|
| < 0.3 | 전선 ≈ 전주 | **A**: catenary 불필요 |
| 0.3~0.7 | 중간 | Prior DA까지 실행 필요 |
| > 0.7 | 전선 ≈ 배경 | **B**: catenary 필요 |

### 출력물

1. 영역별 depth 통계 테이블
2. ratio 값과 방향 판정
3. 시각화 이미지 (RGB + depth + 영역 마커)

## 우선순위

### 사전 실험 (완료)

1. ~~PatchFusion Docker 환경 구축~~ ✅
2. ~~PatchFusion 실행 (1장 테스트 → 전체 180장)~~ ✅
3. ~~이미지 선별 (썸네일 갤러리)~~ ✅
4. ~~웹 기반 region selector 생성~~ ✅
5. ~~분석 스크립트 실행 → 방향 A 채택~~ ✅

### 본 실험 (진행 예정)

상세 계획: `docs/experiment_plan.md`

6. COLMAP SfM/MVS 처리
7. Sparse point 분석 (전주 위치 확인)
8. Prior Depth Anything 실행
9. 전선 depth 품질 평가
10. 정량 평가 및 ablation
11. 논문 작성

## 코딩 규칙

- Python 3.10+
- Docker 기반 실행 (PatchFusion)
- depth 파일: .npy (numpy float32)
- 웹 페이지: vanilla HTML/JS/CSS (프레임워크 불필요)
- 시각화: matplotlib (dpi=200)
- 8192x5460 이미지를 웹에서 표시할 때 성능 고려 (다운샘플된 표시용 이미지 + 원본 좌표 변환)

## 논문 맥락 (참고)

- 확장초록은 ISPRS 2026 accept됨. 풀페이퍼 제출 기한 촉박.
- 리뷰어 핵심 지적: 정량적 평가 부재, ablation 부재, 방법론 세부 기술 부족.
- 방향 A: "MVS + foundation model만으로 해결" → 더 범용적
- 방향 B: "catenary physics prior + foundation model" → power line 특화, novelty 더 강함
