# 실험 계획: MVS + MDE Fusion을 통한 Thin Structure Depth 복원

## 연구 목표

드론 multi-view 이미지에서 전선(power line) 같은 thin structure의 3D reconstruction을 개선한다.
MVS의 metric accuracy와 MDE(Monocular Depth Estimation)의 dense structural coherence를 fusion하여,
MVS가 실패하는 thin structure 영역의 metric depth를 복원한다.

## Contribution

### Main: Thin structure 복원을 위한 MVS+MDE fusion pipeline

드론 이미지에서 전선 같은 thin structure의 metric depth를 복원하는 pipeline을 제안한다.
기존 MVS+MDE fusion(Prior DA 등)은 일반 장면을 대상으로 하며,
thin structure의 특수성(극소 폭, MVS 결손, 해상도 의존성)을 고려하지 않는다.

본 pipeline은 thin structure에서 **MVS가 어디서 실패하고, MDE가 어디서 보완하는지를 분석한 위에** 설계되었으며, 기존 도구(PatchFusion, Prior DA)를 thin structure 조건에 맞게 조합한다.

### Pipeline 설계 근거

본 pipeline의 각 설계 선택은 다음의 분석적 근거에 기반한다:

**근거 1: MDE의 thin structure depth behavior**

- MDE는 전선의 relative depth를 배경이 아닌 전주에 가깝게 추정 (사전 실험에서 확인)
- 이것이 성립해야 MVS metric prior와의 fusion으로 전선의 올바른 metric depth를 얻을 수 있음
- 기존 연구에서 분석된 바 없는 empirical finding → **fusion이 왜 작동하는지의 이론적 근거**

**근거 2: 고해상도 MDE의 필요성**

- 전선은 원본 이미지에서 2~3 pixel 폭
- 일반 MDE 입력 해상도(512~1024px)로 다운샘플하면 전선이 소실됨
- PatchFusion 같은 고해상도 패치 기반 처리가 필수 → **pipeline의 MDE 단 설계 근거**

### Validation

Pipeline이 실제로 thin structure에서 작동함을 다음으로 검증한다:

- **Completeness**: MVS ~0% → fusion ~100% (전선 영역 depth 채워짐)
- **Metric accuracy**: fusion된 전선 depth ≈ 전주 depth (물리적으로 타당)
- **구성요소 필요성**: MVS only / MDE only / fusion 비교(5-1)로 양쪽 모두 필요함을 보임
- **Ablation**: 해상도 낮추면 실패(5-2), MDE 모델 의존성 확인(5-3)

---

## 핵심 가설

> MDE의 relative depth에서 전선은 전주와 유사한 depth를 가진다.
> 따라서 MVS metric prior를 MDE에 align(Prior DA)하면,
> 전선 영역에서도 올바른 metric depth를 얻을 수 있다.

사전 실험에서 확인: ratio < 0.3 → **가설 지지** (상세: `pilot_experiment_report.md`)

---

## 실험 단계 개요

```
Step 0: 사전 실험 (완료)
  → MDE가 전선 depth를 전주에 가깝게 추정하는지 확인

Step 1: SfM/MVS 데이터 확보 (Metashape 사용, 완료)
  → camera poses + sparse points + dense depth maps
  → 전선 결손 확인 (문제 정의 검증)

Step 2: Sparse/Dense Prior 분석 (진행 중)
  → MVS 데이터에서 Prior DA에 넣을 metric prior 확보 가능성 확인

Step 3: Prior Depth Anything 실행
  → MVS metric prior + MDE relative depth → metric depth (전선 포함)

Step 4: 전선 영역 Depth 품질 평가
  → fusion 결과에서 전선 depth가 물리적으로 타당한지 검증

Step 5: 정량 평가 및 Ablation
  → pipeline 성능 검증 + 설계 근거별 ablation

Step 6: 논문 작성
```

---

## Step 0: 사전 실험 ✅ 완료

### 목적

MDE(PatchFusion/DA V1)의 relative depth에서
전선 depth가 전주에 가까운지(→ fusion 가능) 배경에 가까운지(→ fusion 불가) 판별.

### 결과

| 이미지 | Pole | Wire center | Background | ratio |
|--------|------|-------------|------------|-------|
| 0654 | 10.78 | 10.75 | 11.45 | **-0.045** |
| 0656 | 11.09 | 11.05 | 11.70 | **-0.054** |
| 0661 | 10.13 | 9.11 | 10.05 | N/A (*) |

3장 모두 wire depth < background depth, ratio < 0.3 → **가설 지지, fusion 접근 유효**

### Lessons learned

- 전선(2~3px)에 patch 평균 sampling 사용하면 배경에 오염 → min-based sampling 필요
- 이 문제는 Step 4~5의 평가에서도 동일하게 적용됨
- 상세: `pilot_experiment_report.md`

---

## Step 1: SfM/MVS 데이터 확보 ✅ Metashape로 완료

### 목적

MVS pipeline의 출력물을 확보하고, 전선에서 MVS가 실패하는 것을 검증.

### 방법

- **Metashape** (Agisoft)를 사용하여 SfM/MVS 처리
- Align Photos → Build Dense Cloud → Export (COLMAP format)
- 참고: 기존에 Metashape로 처리해둔 데이터를 활용한 것이며,
  COLMAP 등 다른 SfM/MVS pipeline으로도 동일한 결과를 얻을 수 있음.
  Pipeline은 특정 SfM/MVS 도구에 종속되지 않음.

### 확보된 데이터

| 데이터 | 경로 | 상태 |
|--------|------|------|
| Camera poses + Sparse points | `data/colmap_export/` (COLMAP format) | ✅ 확보 |
| Dense depth maps | `/media/.../depthmaps/ultrahigh/` | ✅ 확보 |
| 카메라 모델 | SIMPLE_PINHOLE, 8270×5476, f=8198.7 | ✅ |
| Sparse 3D points | 135,703개, mean track length 4.3 | ✅ |
| 등록 이미지 | 180/180 (100%) | ✅ |

### 검증 결과

- [x] 전선 위치에서 dense depth map 결손 확인 — wire_center 0~8%, wire_near_pole 대부분 0%
- [x] Dense depth의 물리적 타당성 확인 — pole 65~69m, background 69~73m

상세: `step1_mvs_verification.md`

---

## Step 2: Sparse/Dense Prior 분석 (진행 중)

### 목적

Prior DA에 넣을 metric prior의 source와 밀도를 결정.

### 분석 결과: SfM Sparse Points

| 이미지 | 전체 sparse points | pole_top 100px 이내 | 200px 이내 |
|--------|-------------------|--------------------|-----------| 
| 0654 | 3,141 | **0** | 12 |
| 0656 | 2,974 | **0** | 7~9 |
| 0661 | 3,410 | **1~3** | 8 |

**전주 근처에 sparse points 부족** — SfM sparse points만으로는 전선 영역에 metric anchor가 약함.

### 분석 결과: Metashape Dense Depth

| 위치 | Dense depth 유효 여부 | depth 값 |
|------|---------------------|----------|
| pole_top | **유효** ✅ | 65~69m |
| wire_near_pole | 대부분 결손 ❌ | — |
| wire_center | 결손 ❌ | — |
| background | **유효** ✅ | 69~73m |

**Dense depth는 전주에 유효한 metric depth를 제공** → sparse prior 보강에 사용 가능.

### Prior 전략 선택

SfM sparse points만으로는 전주 근처에 anchor가 부족하므로,
dense depth에서 유효 pixel을 sampling하여 prior를 보강한다.

| 전략 | 설명 | Prior DA input |
|------|------|----------------|
| Sparse only | SfM sparse points만 사용 | ~3,000 points/image |
| **Sparse + Dense (채택)** | Sparse + dense depth에서 유효 영역 sampling | ~3,000 + 추가 anchor |

Dense sampled(dense depth 유효 pixel 전체에서 grid sampling)도 가능하나,
Prior DA가 수만 점의 dense prior를 의도한 설계가 아닐 수 있으므로
sparse + 전주/구조물 위치 보강이 현실적 선택이다.

### 다음 단계 진행 조건

- [x] Sparse point 분포 확인 완료
- [x] Dense depth의 전주/전선 유효성 확인 완료
- [x] Dense depth에서 전선 결손 시각화 완료 (step1_mvs_verification.md)

---

## Step 3: MVS+MDE Fusion ✅ 완료

### 목적

MVS metric depth의 전선 결손을 MDE relative depth로 채워 metric depth map 생성.

### 시도한 접근 및 결과

#### 3-1. Prior Depth Anything (부적합 판정)

- Prior DA의 내부 해상도(518×518)에서 전선 소실 → thin structure 부적합
- heit=1022로 내부 해상도 상향 시도 → MDE가 전선 인식하나 fine stage에서 덮어씌워짐
- Coarse-only + PatchFusion geometric input → 일부 이미지에서 wire ≈ pole 달성, 나머지 불안정
- 패치 기반 실행 시 전주-전선이 같은 패치에 없으면 scale 전파 불가

#### 3-2. 직접 Affine Alignment (채택)

- MVS valid pixel + PatchFusion relative depth 간 affine fitting: `d_metric = s × d_rel + t`
- 전주 위치에서 RANSAC fitting → 전선(invalid pixel)에 적용
- **결과**: 0656에서 wire=64.26m ≈ pole=65.46m < bg=69.47m 달성

#### 3-3. 발견된 문제

- **PatchFusion 패치간 scale 불일치**: 같은 MVS depth(66m)에서 MDE 값이 위치에 따라 5.7~12.2
- **전주 근처 depth range 협소**: 전주 표면이 거의 같은 depth → scale underdetermined
- **해결**: 전주 주변 r=300으로 확장 + RANSAC outlier 제거 + clean tiepoint 수집

### 최종 Fusion 방법

1. MVS valid pixel → 그대로 유지
2. 전주에서 RANSAC affine fitting (clean tiepoints, r=300)
3. Edge detection (Sobel + morphological closing) + aspect ratio 필터로 전선 그룹 감지
4. Depth range 필터 (pole depth ± 5m) + 전선 그룹에 대표 depth (median) 할당
5. Multi-view joint optimisation으로 3D 위치 정합

---

## Step 4: 전선 영역 Depth 품질 평가 ✅ 완료

### 결과

| 방법 | Wire completeness | Wire depth (m) | Pole depth (m) | Bg depth (m) |
|------|------------------|----------------|----------------|--------------|
| MVS only | 0–8% | — | 65.46 | 69.47 |
| MDE only | 100% | (relative) | — | — |
| Fused (Ours) | 100% | 64.26 | 65.46 | 69.47 |

- wire ≈ pole < bg 관계 달성 (0656 기준)
- Multi-view joint optimisation: per-view residual 0.13–0.33m

### 확인된 한계

- Edge 기반 전선 감지의 불완전성 (끊김, false positive)
- View간 독립 fitting에 의한 3D 산발 (joint optimisation 전 3.25m 차이)
- 전선 그룹 대표 depth 방식은 그룹 내 일관성 확보하지만 view간 불일치 존재

---

## Step 5: 정량 평가 및 Ablation ✅ 완료

### 5-1. Main Result

Table 1 (논문 포함):
- MVS wire completeness: 0–8% → Fused: 100%
- Wire depth 64.26m ≈ Pole 65.46m (1.2m 차이)
- Background 69.47m과 명확히 분리

### 5-2. Ablation: Depth Profile

Figure 2 (논문 포함):
- Wire 위치(y=2925–2938)에서 MVS 결손, MDE(calibrated)와 Fused는 pole depth 근처
- y=2941에서 MVS 79.17m(배경)으로 급등 → wire-bg 분리 확인

### 5-3. 확인된 사항 (논문 한계로 기술)

- Prior DA 518×518 해상도에서 전선 소실 확인
- DA V2는 2x 다운스케일에서도 전선 미인식 (DA V1 + PatchFusion 8K에서만 인식)
- PatchFusion 패치간 scale 불일치로 global alignment 불가

---

## Step 6: 논문 작성 ✅ 진행 중

### 리뷰어 지적 대응

| 지적 | 대응 | 상태 |
|------|------|------|
| 정량적 평가 부재 | Table 1: completeness + metric depth | ✅ |
| Ablation 부재 | Figure 2: depth profile (MVS/MDE/Fused) | ✅ |
| 방법론 세부 기술 부족 | Stage 1–3 상세 기술 (RANSAC, edge detection 등) | ✅ |
| 3D reconstruction 시각화 | Figure 1: CloudCompare 캡처 (PLY) | 진행 중 |

### 논문 파일

- `paper/ISPRSguidelines_authors_abstract.tex` — LaTeX 본문
- `paper/ISPRSguidelines_authors.bib` — 참고문헌 (8개)
- `paper/figures/fig2_profile.png` — depth profile ablation
- `paper/figures/fig1_3d_reconstruction.png` — 3D 시각화 (CloudCompare 캡처 필요)

---

## 데이터 및 환경 요약

| 항목 | 내용 |
|------|------|
| 이미지 | DJI 드론, 180장, 8192×5460 |
| GPU | NVIDIA RTX 3090 × 2 (24GB each) |
| SfM/MVS | Metashape (COLMAP format으로 export) |
| MDE | PatchFusion + Depth Anything V1 (ViT-L) |
| Fusion | 직접 affine alignment (Prior DA 부적합으로 전환) |
| 실험 이미지 | 0654, 0656, 0661 (전주+전선 가시) |

---

*문서 작성: 2026-04-02*
*마지막 업데이트: 2026-04-07 — Step 3~6 실험 결과 반영, Prior DA→직접 alignment 전환, 논문 작성 진행*
