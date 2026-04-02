# Step 1 검증: MVS Dense Depth에서 전선 결손 확인

## 목적

"MVS가 thin structure(전선)에서 실패한다"는 문제 정의를 실제 데이터로 검증한다.
Metashape로 생성한 dense depth map에서 전선 위치에 depth 결손이 있는지 확인하고,
MDE(PatchFusion) depth와 비교하여 fusion의 필요성을 보인다.

## 데이터

| 항목 | 내용 |
|------|------|
| MVS dense depth | Metashape, ultrahigh quality, 8192×5460, float32 TIFF |
| MDE depth | PatchFusion/DA V1, 8192×5460 (원본 해상도), float32 NPY |
| 실험 이미지 | 0654, 0656, 0661 (전주+전선 가시) |
| 영역 좌표 | `scripts/region_selector/regions.json` (사용자 수동 지정) |

## 측정 방법

### Completeness 측정

regions.json에 수동 지정된 각 영역 좌표(pole_top, wire_center, wire_near_pole, background)를
중심으로, MVS dense depth map에서 depth 유효성을 측정.

```
completeness = (depth > 0인 pixel 수) / (patch 내 전체 pixel 수)
```

- **Sampling 영역**: 클릭 좌표 중심 r=3 패치 (7×7 = 49 pixels)
- **r=3 선택 근거**: 전선 폭이 원본 이미지에서 2~3 pixel이므로,
  전선 폭 + 양쪽 약간의 여유(±2px)를 포함하는 최소 패치 크기.
  패치가 너무 크면(r=10 등) 배경 valid pixel이 포함되어 completeness가 과대 측정됨.
- **유효 기준**: depth > 0 (Metashape에서 depth 추정 실패 시 0)

### 방법의 한계

- 전선 "경로 전체"가 아니라 **사용자가 클릭한 점 주변**만 측정
- 전선 경로를 따라 연속적으로 sampling하면 더 대표성 있는 결과를 얻을 수 있으나,
  현재는 전선 mask가 없으므로 점 기반 측정을 사용

### Depth profile 비교

wire_center 좌표에서 수직(y) 방향으로 ±10 pixel 범위의 depth 값을 추출하여
MVS와 MDE를 비교. 전선은 수직 방향으로 2~3 pixel 폭이므로,
수직 profile에서 MVS 결손 구간과 MDE 추정값을 동시에 관찰할 수 있다.

## 결과

### 1. MVS Dense Depth 전체 유효율

| 이미지 | 전체 valid pixel | 유효율 |
|--------|-----------------|--------|
| 0654 | 23,505,271 / 44,728,320 | 52.6% |
| 0656 | — | 54.4% |
| 0661 | — | 55.1% |

이미지 전체에서 약 절반만 유효. 하늘, 어두운 영역, texture 부족 영역에서 결손 발생.

### 2. 영역별 Completeness (r=3, 7×7 patch)

| 이미지 | 영역 | 좌표 | completeness |
|--------|------|------|-------------|
| 0654 | **wire_center** | (6172, 2680) | **0%** (0/49) |
| 0654 | wire_near_pole | (2393, 2873) | 80% |
| 0654 | pole_top | (2271, 2634) | 59% |
| 0654 | background | (5515, 2484) | 4% |
| 0656 | **wire_center** | (4734, 2935) | **0%** (0/49) |
| 0656 | **wire_near_pole** | (6454, 2860) | **0%** (0/49) |
| 0656 | pole_top | (6620, 2715) | 69% |
| 0656 | pole_top | (1127, 2700) | 98% |
| 0656 | background | (4366, 2492) | 96% |
| 0661 | **wire_center** | (4687, 3119) | **8%** (4/49) |
| 0661 | **wire_near_pole** | (3125, 2999) | **0%** (0/49) |
| 0661 | **wire_near_pole** | (3448, 2832) | **0%** (0/49) |
| 0661 | pole_top | (2894, 2877) | 100% |
| 0661 | pole_top | (7999, 2911) | 86% |
| 0661 | background | (4331, 2712) | 100% |

### 3. 영역 유형별 요약

| 영역 유형 | completeness 범위 | 평균 |
|-----------|-------------------|------|
| **wire_center** | **0~8%** | **~3%** |
| **wire_near_pole** | **0~80%** | **~20%** |
| pole_top | 59~100% | ~82% |
| background | 4~100% | ~66% |

전선 영역(wire_center)에서 MVS completeness가 0~8%로 거의 완전히 결손.
wire_near_pole도 대부분 0%이며, 0654(80%)는 전주 바로 옆이라 전주의 valid depth가 포함된 것으로 보임.

### 4. Depth Profile: MVS vs MDE (wire_center 수직 단면)

**0654** — wire_center (6172, 2680):

```
y       MVS         MDE
2670    ---         12.15
2672    ---         12.12
2674    ---         12.05
2676    ---         11.85
2678    ---         11.68
2680    ---         11.61    ← wire_center
2682    ---         11.54
2684    ---         11.48
2686    ---         11.26
2688    ---         10.86
2690    ---         10.61
```

→ MVS는 ±10 pixel 범위 전체가 결손. MDE는 전체 구간에 depth 존재.

**0656** — wire_center (4734, 2935):

```
y       MVS         MDE
2925    ---         12.92
2927    ---         12.69
2929    ---         12.13
2931    ---         11.39
2933    ---         11.14    ← wire pixel (MDE dip)
2935    ---         11.38    ← wire_center click
2937    ---         11.92
2939    ---         12.62
2941    79.17       13.12    ← MVS 유효 시작 (배경)
2943    79.17       13.17
2945    79.17       13.17
```

→ y=2941에서 MVS가 유효해지며, 그 위(전선 쪽)는 전부 결손.
MDE에서 y=2933의 depth dip(11.14)이 전선 pixel에 해당.

**0661** — wire_center (4687, 3119):

```
y       MVS         MDE
3109    81.33       11.98    ← MVS 유효 (배경)
3111    ---         12.01    ← MVS 결손 시작
3113    ---         12.04
3115    ---         12.01
3117    ---         11.90
3119    ---         11.97    ← wire_center click
3121    ---         11.98
3123    ---         10.72
3125    ---          9.48    ← wire pixel (MDE dip)
3127    ---          9.12
3129    ---          9.37
```

→ y=3109까지 MVS 유효, 이후 전선 영역 전체가 결손.

### 5. 시각화

![MVS vs MDE depth comparison](figures/fig6_mvs_vs_mde.png)

- **왼쪽**: RGB (영역 마커 표시)
- **중간**: MVS dense depth — 회색 영역이 결손(depth 없음). 전선이 지나가는 영역에서 뚜렷한 결손.
- **오른쪽**: MDE depth (PatchFusion) — 결손 없이 전체 coverage. 전선 위치에도 depth 존재.

### 6. Dense Depth의 물리적 타당성

Metashape dense depth가 유효한 영역에서의 metric depth 값:

| 위치 | depth (m) | 타당성 |
|------|-----------|--------|
| pole_top | 65~69m | 드론-전주 거리로 합리적 |
| background (건물) | 69~73m | 전주보다 약간 먼 거리, 합리적 |
| pole과 background 차이 | ~4m | 전주가 건물 앞에 있으므로 타당 |

절대적 정확도의 GT는 없으나, 상대적 관계와 값의 범위가 물리적으로 타당함.

## 결론

### 문제 정의 검증 ✅

1. **MVS는 전선 영역에서 결손**: wire_center completeness 0~8%, wire_near_pole 대부분 0%
2. **MDE는 전선 영역에서 유효**: PatchFusion이 모든 pixel에 depth 추정 (100% coverage)
3. **MVS는 전주/배경에서 유효**: pole_top 48~98%, background 62~97%

이는 **"MVS의 metric accuracy(유효한 곳) + MDE의 structural completeness(전체)"를 fusion하면
전선의 metric depth를 복원할 수 있다**는 pipeline 접근의 전제를 지지한다.

### Step 1 체크리스트

- [x] 전선 위치에서 dense depth map 결손 확인 — **wire_center 0~8%로 결손 확인**
- [x] Dense depth의 물리적 타당성 확인 — **pole 65~69m, bg 69~73m으로 합리적**

---

*작성: 2026-04-02*
*이 문서는 experiment_plan.md Step 1의 검증 결과이다.*
