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
- [ ] Dense depth에서 전선 결손 시각화 (Step 1 검증)

---

## Step 3: Prior Depth Anything 실행

### 목적

MVS metric prior와 MDE relative depth를 fusion하여
전선 영역을 포함한 전체 이미지의 metric depth map을 생성.

### 확인하고자 하는 것

1. **Fusion 수렴**: prior 위치에서 metric depth가 정확히 반영되는가?
2. **전선 depth 전파**: MDE가 전선≈전주로 추정하므로, metric align 후에도 유지되는가?
3. **배경 분리**: 전선과 배경 건물의 metric depth가 명확히 구분되는가?

### 방법

- Prior Depth Anything 공식 구현 사용
- Prior DA는 자체 MDE backbone으로 relative depth를 생성하고,
  MVS metric points를 prior로 받아 metric depth로 변환
- Input: RGB 이미지 + MVS metric points (sparse 및/또는 dense sampled)
- Output: per-image metric depth map

### Prior input 구성

- COLMAP export의 SfM sparse points (기본)
- Metashape dense depth에서 추출한 추가 points (보강)
  - 전주 위치, 건물 벽면, 도로면 등 유효 영역에서 sampling
  - 전선 결손 영역은 제외 (dense depth가 없으므로)

### 기대 결과

- Prior 위치: fusion depth ≈ MVS metric depth
- 전선 위치: fusion depth ≈ 전주 depth (사전 실험 가설에 의해)
- 배경 위치: fusion depth > 전선/전주 depth

### 다음 단계 진행 조건

- [ ] Prior 위치에서 fusion depth와 MVS depth의 차이 < 5%
- [ ] 전선 위치에서 fusion depth가 전주 depth와 유사 (ratio < 0.3)
- [ ] 전선-배경 depth 분리 확인

### 실패 시

- 전선 depth가 배경에 가까움 → prior 밀도 증가 시도, 그래도 실패하면 방향 B 재고려
- Fusion 불안정 → Prior DA 파라미터 조정 (prior weight 등)

---

## Step 4: 전선 영역 Depth 품질 평가

### 목적

Fusion 결과에서 전선 영역의 depth가 물리적으로 타당하고
downstream task(3D reconstruction)에 사용 가능한지 평가.

### 확인하고자 하는 것

1. **전선의 depth 연속성**: 전주에서 전선 중앙까지 depth가 부드럽게 변하는가?
2. **물리적 타당성**: 전선 depth가 전주 depth와 유사하고 배경보다 가까운가?
3. **MVS 대비 개선**: MVS에서 결손이었던 전선 영역이 fusion에서 채워졌는가?

### 방법

1. 전주에서 전선 중앙까지 depth profile 추출 (line scan)
2. MVS depth vs fusion depth를 전선 영역에서 비교
3. Depth map completeness: 전선 mask 영역에서 valid pixel 비율

### 다음 단계 진행 조건

- [ ] 전선 영역 completeness: fusion > 90% (MVS는 ~0%)
- [ ] Depth profile이 물리적으로 타당 (급격한 불연속 없음)
- [ ] 전선 depth가 전주 ± 20% 이내

---

## Step 5: 정량 평가 및 Ablation

### 목적

Pipeline이 thin structure에서 작동함을 정량적으로 검증하고,
각 구성요소(고해상도 MDE, metric prior)의 필요성을 ablation으로 입증.

### 5-1. Main Result: Pipeline 성능

전선 영역에서 각 방법의 depth completeness + metric accuracy 비교.

| 방법 | completeness | metric accuracy | 비고 |
|------|-------------|-----------------|------|
| MVS only | ~0% (결손) | 유효 pixel은 정확 | 전선에 구멍 |
| MDE only | ~100% | scale 없음 | 구조는 있으나 metric 아님 |
| **Fusion (ours)** | ~100% | metric scale 보정됨 | 전선 depth 복원 |

→ Pipeline이 MVS의 metric accuracy와 MDE의 structural completeness를 모두 확보.

### 5-2. Ablation: MDE 해상도 (근거 2 검증)

Pipeline에서 고해상도 MDE가 필수적인지 검증.

| 구성 | MDE 해상도 | 전선 인식 | fusion 후 전선 depth |
|------|-----------|----------|---------------------|
| Full pipeline | 8192×5460 (PatchFusion) | ✅ 보존 | (측정) |
| 다운샘플 MDE | 2048×1365 | ? 흐릿 | (측정) |
| 다운샘플 MDE | 1024×682 | ❌ 소실 | (측정) |

→ 해상도를 낮추면 MDE가 전선을 인식하지 못해 fusion이 실패하는 것을 보임.

### 5-3. Ablation: MDE 모델 종류 (근거 1 검증)

"MDE가 전선 depth를 전주에 가깝게 추정한다"는 finding이 특정 모델에 한정적인지 확인.

| MDE | wire-pole ratio | fusion 후 전선 depth |
|-----|----------------|---------------------|
| Depth Anything V1 (ViT-L) | <0.3 (사전실험 확인) | (측정) |
| Depth Anything V2 (ViT-L) | (측정) | (측정) |

→ Finding이 일반적이면 pipeline의 범용성 강화, 모델 의존적이면 한계로 기술.

### 5-4. Multi-view Consistency (선택)

- 동일 전선을 다른 view에서 관찰했을 때 depth 일관성
- 3D reprojection error at wire locations

---

## Step 6: 논문 작성

### 리뷰어 지적 대응

| 지적 | 대응 | 해당 Step |
|------|------|-----------|
| 정량적 평가 부재 | 5-1 completeness/accuracy | Step 5 |
| Ablation 부재 | 5-2 해상도, 5-3 MDE 모델 | Step 5 |
| 방법론 세부 기술 부족 | pipeline 전체 상세 기술 | Step 1-4 |

### 논문 구조 (예상)

1. **Introduction**: thin structure의 MVS 한계, MDE 가능성, 연구 목적
2. **Related Work**: MVS, MDE (DA, PatchFusion), MVS+MDE fusion (Prior DA)
3. **Analysis**: MDE의 thin structure depth behavior (근거 1) + 고해상도 필요성 (근거 2)
4. **Method**: Pipeline 설계 — SfM/MVS → metric prior 추출 → Prior DA fusion
5. **Experiments**: completeness/accuracy (5-1), ablation (5-2, 5-3)
6. **Discussion**: 한계, MDE 모델 의존성, 다른 thin structure로의 확장 가능성
7. **Conclusion**

---

## 데이터 및 환경 요약

| 항목 | 내용 |
|------|------|
| 이미지 | DJI 드론, 180장, 8192×5460 |
| GPU | NVIDIA RTX 3090 × 2 (24GB each) |
| SfM/MVS | Metashape (COLMAP format으로 export) |
| MDE | PatchFusion + Depth Anything V1 (ViT-L) |
| Fusion | Prior Depth Anything |
| 실험 이미지 | 0654, 0656, 0661 (전주+전선 가시) |

---

## 리스크 및 대안

| 리스크 | 확률 | 대안 |
|--------|------|------|
| Prior DA에서 전선 depth 전파 실패 | 중간 | dense prior 보강, prior weight 조정 |
| Prior DA 구현 호환 문제 | 중간 | 논문 저자 코드 확인, 직접 구현 |
| 고해상도에서 Prior DA OOM | 중간 | 패치 기반 처리, 해상도 조정 |
| 다운샘플에서도 전선 보존됨 (근거 2 약화) | 낮음 | 해상도별 정량 비교로 차이 입증 |

---

*문서 작성: 2026-04-02*
*마지막 업데이트: 2026-04-02 — pipeline을 main contribution으로 재구성, 설계 근거(MDE behavior, 해상도) 명시, ablation을 근거 검증 중심으로 정리*
