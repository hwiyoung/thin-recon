"""
Step 2: 사전 실험 분석 — PatchFusion relative depth에서 전선/전주/배경 비교.

두 가지 모드:
  interactive: 이미지 위 클릭으로 영역 지정 (GUI 필요)
  headless: JSON 파일로 좌표 제공 (서버/Docker에서 사용)

Usage:
    # Interactive
    python analyze_depth.py \
        --rgb /data/images/DJI_xxx.JPG \
        --depth /data/depth_output/DJI_xxx_depth.npy \
        --mode interactive

    # Headless
    python analyze_depth.py \
        --rgb /data/images/DJI_xxx.JPG \
        --depth /data/depth_output/DJI_xxx_depth.npy \
        --regions regions.json \
        --mode headless
"""

import argparse
import json
import os

import cv2
import matplotlib.pyplot as plt
import numpy as np


def sample_region(depth_map, center_xy, radius=5):
    x, y = int(center_xy[0]), int(center_xy[1])
    h, w = depth_map.shape[:2]
    patch = depth_map[
        max(0,y-radius):min(h,y+radius+1),
        max(0,x-radius):min(w,x+radius+1)
    ].flatten()
    valid = patch[np.isfinite(patch) & (patch > 0)]
    return valid


def analyze_regions(depth_map, regions):
    results = {}
    for name, points in regions.items():
        all_vals = []
        for pt in points:
            vals = sample_region(depth_map, pt, radius=5)
            all_vals.extend(vals.tolist())
        all_vals = np.array(all_vals)
        if len(all_vals) == 0:
            results[name] = {"mean": float("nan"), "std": float("nan"), "n": 0}
        else:
            results[name] = {
                "mean": float(np.mean(all_vals)),
                "median": float(np.median(all_vals)),
                "std": float(np.std(all_vals)),
                "min": float(np.min(all_vals)),
                "max": float(np.max(all_vals)),
                "n": len(all_vals),
            }
    return results


def interactive_select(rgb_path):
    img = cv2.imread(rgb_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read: {rgb_path}")

    regions = {
        "pole_top": [],
        "wire_near_pole": [],
        "wire_center": [],
        "background": [],
        "sky": [],
    }
    current_region = ["pole_top"]
    colors = {
        "pole_top": (0, 0, 255),
        "wire_near_pole": (0, 165, 255),
        "wire_center": (0, 255, 255),
        "background": (255, 0, 0),
        "sky": (255, 255, 255),
    }
    display = img.copy()

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            name = current_region[0]
            regions[name].append([x, y])
            cv2.circle(display, (x, y), 8, colors[name], -1)
            cv2.putText(display, name[:4], (x+10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[name], 1)
            cv2.imshow("Select Regions", display)
            print(f"  [{name}] ({x}, {y})")

    print("\n=== 영역 선택 ===")
    print("키를 눌러 영역 전환:")
    print("  1=pole_top  2=wire_near_pole  3=wire_center  4=background  5=sky")
    print("  q=완료")

    cv2.namedWindow("Select Regions", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Select Regions", on_mouse)
    cv2.imshow("Select Regions", display)

    key_map = {
        ord("1"): "pole_top",
        ord("2"): "wire_near_pole",
        ord("3"): "wire_center",
        ord("4"): "background",
        ord("5"): "sky",
    }

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key in key_map:
            current_region[0] = key_map[key]
            print(f"  → {current_region[0]}")
        elif key == ord("q"):
            break

    cv2.destroyAllWindows()
    return regions


def interpret_results(results):
    pole = results.get("pole_top", {}).get("mean", float("nan"))
    wire_near = results.get("wire_near_pole", {}).get("mean", float("nan"))
    wire_center = results.get("wire_center", {}).get("mean", float("nan"))
    bg = results.get("background", {}).get("mean", float("nan"))

    print("\n" + "=" * 60)
    print("  분석 결과")
    print("=" * 60)
    print(f"  Pole depth:         {pole:.4f}")
    print(f"  Wire (near pole):   {wire_near:.4f}")
    print(f"  Wire (center):      {wire_center:.4f}")
    print(f"  Background:         {bg:.4f}")

    if any(np.isnan(v) for v in [pole, wire_center, bg]):
        print("\n  [!] 일부 영역에 유효한 값이 없습니다.")
        return

    if abs(bg - pole) < 1e-8:
        print("\n  [!] Pole과 Background depth 차이가 없습니다.")
        return

    ratio_center = (wire_center - pole) / (bg - pole)
    ratio_near = (wire_near - pole) / (bg - pole)

    print(f"\n  Wire (near pole) ratio: {ratio_near:.3f}")
    print(f"  Wire (center) ratio:    {ratio_center:.3f}")
    print(f"    (0.0 = pole과 동일, 1.0 = background와 동일)")

    print("\n  " + "-" * 40)
    if ratio_center < 0.3:
        print("  ★ 방향 A 유력: 전선 depth가 전주에 가까움")
        print("    → catenary 불필요, Prior DA에 MVS sparse만으로 충분할 가능성")
    elif ratio_center < 0.7:
        print("  ★ 불명확: 전선 depth가 전주와 배경 사이")
        print("    → Prior DA 실행해봐야 확정 가능")
        if ratio_near < 0.3:
            print("    → 전주 근처는 가까움, 중앙은 멀어짐 — catenary가 유효할 수 있음")
    else:
        print("  ★ 방향 B 유력: 전선 depth가 배경에 가까움")
        print("    → catenary prior 필요")

    print("=" * 60)
    return {"ratio_near": ratio_near, "ratio_center": ratio_center}


def plot_results(rgb_path, depth_map, regions, output_dir):
    # Depth map visualization
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    rgb = cv2.imread(rgb_path)
    rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
    axes[0].imshow(rgb)
    axes[0].set_title("RGB + Regions")

    colors_plt = {
        "pole_top": "red",
        "wire_near_pole": "orange",
        "wire_center": "yellow",
        "background": "blue",
        "sky": "white",
    }
    for name, points in regions.items():
        for pt in points:
            axes[0].plot(pt[0], pt[1], 'o', color=colors_plt.get(name, 'green'),
                        markersize=8, label=name)

    # Remove duplicate labels
    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes[0].legend(by_label.values(), by_label.keys(), fontsize=8)

    valid_depth = depth_map.copy()
    valid_depth[~np.isfinite(valid_depth) | (valid_depth <= 0)] = np.nan
    axes[1].imshow(valid_depth, cmap='viridis')
    axes[1].set_title("PatchFusion Relative Depth")

    plt.tight_layout()
    path = os.path.join(output_dir, "region_overview.png")
    fig.savefig(path, dpi=200)
    print(f"Plot saved: {path}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="사전 실험: 전선/전주/배경 depth 비교")
    parser.add_argument("--rgb", required=True)
    parser.add_argument("--depth", required=True, help=".npy depth map from PatchFusion")
    parser.add_argument("--regions", default=None, help="JSON file with pre-defined regions")
    parser.add_argument("--mode", default="interactive", choices=["interactive", "headless"])
    parser.add_argument("--output_dir", default="data/analysis")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load depth
    if args.depth.endswith(".npy"):
        depth = np.load(args.depth)
    else:
        depth = cv2.imread(args.depth, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
        if depth.ndim == 3:
            depth = depth[:, :, 0]
    depth = depth.astype(np.float32)
    print(f"Depth loaded: shape={depth.shape}, range=[{depth.min():.2f}, {depth.max():.2f}]")

    # Get regions
    if args.regions and os.path.exists(args.regions):
        with open(args.regions) as f:
            regions = json.load(f)
    elif args.mode == "interactive":
        regions = interactive_select(args.rgb)
    else:
        print("[ERROR] headless mode는 --regions 필요")
        return

    # Save regions
    regions_path = os.path.join(args.output_dir, "regions.json")
    with open(regions_path, "w") as f:
        json.dump(regions, f, indent=2)

    # Analyze
    results = analyze_regions(depth, regions)
    for name, stats in results.items():
        print(f"  {name:20s}: mean={stats['mean']:10.4f}  std={stats['std']:8.4f}  n={stats['n']}")

    # Interpret
    ratios = interpret_results(results)

    # Plot
    plot_results(args.rgb, depth, regions, args.output_dir)

    # Save
    output = {"regions": regions, "stats": results, "ratios": ratios}
    with open(os.path.join(args.output_dir, "results.json"), "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved: {args.output_dir}/results.json")


if __name__ == "__main__":
    main()
