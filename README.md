# thin-recon

ISPRS 2026 논문: 드론 이미지에서 전선(power line) 등 thin structure의 3D reconstruction 개선.

## 연구 방향

MVS가 전선에서 실패(texture 부족 → depth 결손)하는 문제를,
**depth foundation model + MVS sparse metric prior** 로 해결한다.

### 사전 실험 결과 → 방향 A 채택

> Foundation model(PatchFusion/DA V1)은 전선의 depth를 배경이 아닌 **전주에 가깝게** 추정한다.
> → MVS sparse points(전주 포함)만으로 전선 depth 보정 가능. Catenary 물리 모델 불필요.

상세: [`docs/pilot_experiment_report.md`](docs/pilot_experiment_report.md)

## 프로젝트 구조

```
thin-recon/
├── CLAUDE.md                     # 프로젝트 지침
├── Dockerfile                    # PatchFusion Docker 환경
├── docker-compose.yml
├── run_patchfusion.py            # PatchFusion 실행 스크립트
├── patch_patchfusion.py          # PatchFusion from_pretrained 버그 fix
├── analyze_depth.py              # depth 분석 (영역별 비교)
├── docs/
│   ├── pilot_experiment_report.md  # 사전 실험 결과 보고서
│   ├── experiment_plan.md          # 본 실험 계획 (Step 1~6)
│   └── figures/                    # 보고서 시각화
├── scripts/
│   └── region_selector/            # 웹 기반 영역 지정 도구
│       ├── gallery.html            # 이미지 선별 갤러리
│       ├── selector.html           # 전주/전선/배경 클릭 도구
│       └── regions.json            # 선택된 영역 좌표
└── data/                           # (gitignore) 생성 데이터
    ├── depth_output/               # PatchFusion depth maps (.npy)
    ├── depth_vis/                  # depth 시각화 (.png)
    └── thumbnails/                 # 이미지 썸네일
```

## 실험 파이프라인

```
사전 실험 (완료)
  Step 0: PatchFusion → relative depth → 전선/전주/배경 비교 → 방향 A 채택

본 실험 (예정)
  Step 1: COLMAP SfM/MVS → sparse points + camera poses
  Step 2: Sparse point 분석 → 전주 위치에 points 존재 확인
  Step 3: Prior Depth Anything → sparse metric + foundation model → metric depth
  Step 4: 전선 depth 품질 평가
  Step 5: 정량 평가 + ablation
  Step 6: 논문 작성
```

상세: [`docs/experiment_plan.md`](docs/experiment_plan.md)

## 환경

- GPU: NVIDIA RTX 3090 × 2 (24GB)
- Docker 기반 실행 (PatchFusion, COLMAP)
- Python 3.10+
