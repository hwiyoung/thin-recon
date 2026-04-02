# 실험 계획: 방향 A — MVS Sparse Prior + Foundation Model로 전선 Depth 복원

## 연구 목표

드론 multi-view 이미지에서 전선(power line) 같은 thin structure의 3D reconstruction을 개선한다.
MVS가 전선에서 실패하는 문제를, depth foundation model과 MVS sparse metric points의 fusion으로 해결한다.

### 핵심 가설 (방향 A)

> Foundation model의 relative depth에서 전선은 전주와 유사한 depth를 가진다.
> 따라서 MVS sparse points(전주 포함)를 Prior Depth Anything에 넣으면,
> 전주의 metric depth가 전선으로 자연스럽게 전파되어 정확한 metric depth를 얻을 수 있다.

### 방향 A의 장점

- Catenary 같은 도메인 특화 물리 모델이 불필요
- 전선뿐 아니라 thin structure 일반에 적용 가능 → 범용성
- 파이프라인이 단순: SfM/MVS → sparse points 추출 → Prior DA fusion

---

## 실험 단계 개요

```
Step 0: 사전 실험 (완료)
  → foundation model이 전선 depth를 전주에 가깝게 추정하는지 확인

Step 1: SfM/MVS 처리
  → camera poses + sparse 3D points + MVS dense depth maps

Step 2: Sparse Point 분석
  → MVS sparse points가 전주 위치에 존재하는지 확인

Step 3: Prior Depth Anything 실행
  → sparse metric prior + foundation model relative depth → metric depth

Step 4: 전선 영역 Depth 품질 평가
  → Prior DA 출력에서 전선 depth가 물리적으로 타당한지 검증

Step 5: 정량 평가 및 Ablation
  → 논문용 정량적 결과 생성

Step 6: 논문 작성
  → 리뷰어 지적사항 반영한 풀페이퍼
```

---

## Step 0: 사전 실험 ✅ 완료

### 목적

Foundation model(PatchFusion/Depth Anything V1)의 relative depth에서,
전선의 depth가 전주에 가까운지(→ 방향 A) 배경에 가까운지(→ 방향 B) 판별.

### 방법

1. PatchFusion으로 8192×5460 원본 이미지의 고해상도 relative depth map 생성
2. 3장의 이미지에서 전주/전선/배경 영역의 depth 비교
3. ratio = (wire_depth − pole_depth) / (bg_depth − pole_depth) 계산

### 결과

| 이미지 | Pole | Wire center | Background | ratio |
|--------|------|-------------|------------|-------|
| 0654 | 10.78 | 10.75 | 11.45 | **-0.045** |
| 0656 | 11.09 | 11.05 | 11.70 | **-0.054** |
| 0661 | 10.13 | 9.11 | 10.05 | N/A (*) |

(*) 0661은 pole-bg 차이가 0.08로 ratio 분모가 너무 작아 해석 불가.
    단, wire(9.11) < pole(10.13) ≈ bg(10.05)이므로 방향 A와 일관.

### 판정

- 3장 모두 wire depth < background depth (전선이 배경보다 가까움)
- ratio < 0.3 → **방향 A 채택**

### 주의사항 (lessons learned)

- 전선은 2~3 pixel 폭이므로 sampling radius를 크게 잡으면 배경 pixel이 지배함
- wire 영역은 클릭 주변에서 depth 최소값(= 가장 가까운 pixel)을 찾아야 정확

---

## Step 1: SfM/MVS 처리

### 목적

180장의 드론 이미지로부터 3D reconstruction을 수행하여:
- Camera poses (내부/외부 파라미터)
- Sparse 3D point cloud (feature matching 기반)
- Dense MVS depth maps

### 확인하고자 하는 것

1. **SfM 수렴**: 대부분의 이미지가 registration 되는가?
2. **Sparse point 분포**: 전주(pole) 위치에 sparse points가 존재하는가?
3. **MVS depth의 전선 결손**: 전선 위치에서 MVS depth map에 구멍이 있는가?
   - 이것이 확인되어야 "MVS가 전선에서 실패한다"는 문제 정의가 성립

### 방법

- COLMAP을 사용한 SfM → MVS pipeline
- Docker 환경에서 실행
- GPU 가속 (RTX 3090 x2)

### 기대 결과

- SfM: 드론 이미지는 순차 촬영 + 높은 overlap → 대부분 registration 성공 예상
- Sparse points: 건물, 도로, 전주 등 texture가 풍부한 구조물에 집중 분포
- MVS depth: 전선은 texture가 부족하여 matching 실패 → depth map에 빈 영역

### 다음 단계 진행 조건

- [ ] 전체 이미지의 80% 이상이 SfM에 registration
- [ ] Sparse point cloud에서 전주 영역에 3D points 존재 확인
- [ ] MVS depth map에서 전선 위치에 depth 결손 확인 (문제 정의 검증)

### 실패 시

- SfM 실패 → 이미지 품질/overlap 문제. 이미지 subset 선택 또는 파라미터 조정
- 전주에 sparse points 없음 → feature matching 파라미터 조정, 또는 manual sparse point 추가 고려

---

## Step 2: Sparse Point 분석

### 목적

MVS sparse points를 Prior DA의 metric prior로 사용하기 위해,
전주 위치에 충분한 sparse points가 존재하는지 확인.

### 확인하고자 하는 것

1. **전주 위치의 sparse point 밀도**: 전주 표면에 몇 개의 3D points가 있는가?
2. **Depth 정확도**: sparse points의 reprojected depth가 물리적으로 타당한가?
3. **전선 근처 coverage**: 전선 시작/끝점(전주 꼭대기) 부근에 points가 있는가?

### 방법

1. COLMAP sparse point cloud를 각 이미지에 projection
2. Step 0에서 선별한 이미지(0654, 0656, 0661)에 대해 projected points 시각화
3. 전주 영역의 point 밀도 및 depth 값 확인

### 기대 결과

- 전주는 수직 구조물로 texture가 있어 feature matching 가능 → sparse points 존재 예상
- 전주 꼭대기 부근에 최소 수 개의 sparse points → Prior DA의 metric anchor로 사용 가능

### 다음 단계 진행 조건

- [ ] 전주 영역(pole_top 좌표 주변 100px)에 최소 5개 이상의 sparse points
- [ ] Sparse point depth의 일관성 확인 (std / mean < 0.1)

### 실패 시

- 전주에 sparse points 부족 → 
  - COLMAP feature matching 파라미터 완화 (더 많은 features 추출)
  - 또는 semi-dense matching 사용
  - 최악의 경우: manual sparse point annotation 고려

---

## Step 3: Prior Depth Anything 실행

### 목적

MVS sparse metric points(전주 depth 포함)를 prior로,
foundation model의 relative depth를 metric depth로 변환.
전선 영역에서 metric depth가 올바르게 추정되는지 확인.

### 확인하고자 하는 것

1. **Fusion 수렴**: sparse points에서의 metric depth와 fusion 결과가 일치하는가?
2. **전선 depth 전파**: 전주의 metric depth가 전선 영역으로 전파되는가?
3. **배경 depth 분리**: 전선과 배경 건물의 metric depth가 명확히 분리되는가?

### 방법

- Prior Depth Anything 논문의 공식 구현 사용
- Prior DA는 자체 foundation model backbone으로 relative depth를 생성하고,
  MVS sparse metric points를 prior로 받아 metric depth로 변환
- Input: RGB 이미지 + MVS sparse metric points (COLMAP에서 추출)
- Output: per-image metric depth map
- 참고: Step 0의 PatchFusion 출력은 사전 실험(방향 판정)에만 사용.
  Prior DA는 자체 backbone을 사용하므로 별도 inference가 필요

### 기대 결과

- Sparse point 위치에서: Prior DA depth ≈ MVS metric depth (prior가 반영됨)
- 전선 위치에서: Prior DA depth ≈ 전주 depth (방향 A 가설에 의해 전파됨)
- 배경 위치에서: Prior DA depth > 전선/전주 depth (물리적으로 타당)

### 다음 단계 진행 조건

- [ ] Sparse point 위치에서 Prior DA depth와 MVS depth의 차이 < 5%
- [ ] 전선 위치에서 Prior DA depth가 전주 depth와 유사 (ratio < 0.3)
- [ ] 전선 위치에서 Prior DA depth ≠ 배경 depth (명확한 분리)

### 실패 시

- 전선 depth가 여전히 배경에 가까움 →
  - Sparse point 밀도 부족이 원인일 수 있음 → Step 2에서 밀도 증가
  - Foundation model 자체의 한계 → 방향 B(catenary prior) 재고려
- Fusion이 불안정 → Prior DA 파라미터 조정 (sparse point weight 등)

---

## Step 4: 전선 영역 Depth 품질 평가

### 목적

Prior DA가 출력한 metric depth map에서 전선 영역의 depth가
물리적으로 타당하고 downstream task(3D reconstruction)에 사용 가능한지 평가.

### 확인하고자 하는 것

1. **전선의 depth 연속성**: 전주에서 전선 중앙까지 depth가 부드럽게 변하는가?
2. **물리적 타당성**: 전선 depth가 전주 depth와 유사하고 배경보다 가까운가?
3. **MVS 대비 개선**: MVS에서 결손이었던 전선 영역이 Prior DA에서 채워졌는가?

### 방법

1. 전주에서 전선 중앙까지 depth profile 추출 (line scan)
2. MVS depth vs Prior DA depth를 전선 영역에서 비교
3. Depth map completeness 계산: 전선 mask 영역에서 valid pixel 비율

### 기대 결과

- MVS depth: 전선 영역 completeness ~0% (구멍)
- Prior DA depth: 전선 영역 completeness ~100% (채워짐)
- 전선 depth profile: 전주에서 중앙으로 완만하게 변화 (physically plausible)

### 다음 단계 진행 조건

- [ ] 전선 영역 completeness: Prior DA > 90%
- [ ] Depth profile이 물리적으로 타당 (급격한 불연속 없음)
- [ ] 전선 영역에서 depth 값이 전주 ± 20% 이내

---

## Step 5: 정량 평가 및 Ablation

### 목적

논문에 포함할 정량적 결과를 생성. 리뷰어 지적사항 대응:
- 정량적 평가 부재 → metric 제시
- Ablation 부재 → 각 요소의 기여도 분석

### 평가 항목

#### 5-1. Depth Completeness (전선 영역)

| 방법 | 전선 영역 completeness |
|------|----------------------|
| MVS only | ~0% (baseline) |
| Foundation model only | ~100% (but wrong scale) |
| Prior DA (ours) | ~100% (correct scale) |

#### 5-2. Depth Accuracy (sparse point 위치)

| 방법 | MAE | RMSE | δ < 1.05 |
|------|-----|------|----------|
| Foundation model only | (large, wrong scale) | | |
| Prior DA (ours) | (small, correct scale) | | |

Ground truth: MVS sparse points at known locations (self-supervised evaluation)

#### 5-3. Ablation Study

| 실험 | 변수 | 목적 |
|------|------|------|
| A1 | Sparse point 밀도 (100%, 50%, 25%, 10%) | Prior 밀도의 영향 |
| A2 | 전주 points 제거 | 전주 depth 전파의 기여도 |
| A3 | Foundation model 종류 (DA V1 vs V2) | 모델 의존성 |
| A4 | 이미지 해상도 (원본 vs downsampled) | PatchFusion의 기여도 |

#### 5-4. Multi-view Consistency (선택)

- 동일 전선을 다른 view에서 관찰했을 때 depth 일관성
- 3D reprojection error at wire locations

### 다음 단계 진행 조건

- [ ] Completeness, accuracy 숫자가 논문에 설득력 있는 수준
- [ ] Ablation에서 각 요소의 기여가 명확히 드러남
- [ ] 최소 3개 이상의 이미지에서 일관된 결과

---

## Step 6: 논문 작성

### 리뷰어 지적 대응

| 지적 | 대응 | 해당 Step |
|------|------|-----------|
| 정량적 평가 부재 | Step 5의 completeness, accuracy metrics | Step 5 |
| Ablation 부재 | Step 5의 ablation study (A1-A4) | Step 5 |
| 방법론 세부 기술 부족 | 전체 pipeline 상세 기술 | Step 1-4 |

### 논문 구조 (예상)

1. Introduction: thin structure 문제 정의
2. Related Work: MVS, depth foundation models, Prior DA
3. Method: SfM/MVS → sparse prior 추출 → Prior DA fusion
4. Experiments: Step 4-5 결과
5. Discussion: 방향 A의 한계, 일반화 가능성
6. Conclusion

---

## 데이터 및 환경 요약

| 항목 | 내용 |
|------|------|
| 이미지 | DJI 드론, 180장, 8192×5460 |
| GPU | NVIDIA RTX 3090 × 2 (24GB each) |
| SfM/MVS | COLMAP (Docker) |
| Foundation Model | PatchFusion + Depth Anything V1 (ViT-L) |
| Prior DA | Prior Depth Anything (구현 확인 필요) |
| 실험 이미지 | 0654, 0656, 0661 (전주+전선 가시) |

---

## 리스크 및 대안

| 리스크 | 확률 | 대안 |
|--------|------|------|
| 전주에 sparse points 부족 | 낮음 | feature 수 증가, semi-dense |
| Prior DA에서 전선 depth 전파 실패 | 중간 | sparse point 밀도 증가, 방향 B 전환 |
| COLMAP SfM 실패 | 낮음 | 이미지 subset, 파라미터 조정 |
| Prior DA 구현 호환 문제 | 중간 | 논문 저자 코드 확인, 직접 구현 |

---

*문서 작성: 2026-04-02*
*사전 실험 완료 기준으로 방향 A 채택*
