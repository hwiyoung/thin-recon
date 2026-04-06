"""
MVS + MDE Depth Fusion — 전선 선택적 hole filling.

1. 전주에서 local scale/shift fitting (RANSAC)
2. MDE depth에서 전선 감지 (edge + aspect ratio)
3. Depth range 필터 (전주 depth ± tolerance)
4. 조건 만족하는 pixel만 calibrated MDE로 채움
5. 3D point cloud 출력

Usage:
    python scripts/fuse_depth.py \
        --mde data/depth_output/DJI_xxx_depth.npy \
        --mvs /path/to/depthmaps/DJI_xxx.tif \
        --rgb /path/to/images/DJI_xxx.JPG \
        --pole_coords 6620,2715 \
        --output_dir data/fused_output
"""

import argparse
import os
import numpy as np
from PIL import Image
import cv2
from sklearn.linear_model import RANSACRegressor, LinearRegression


def fit_scale_shift(mvs, mde, px, py, radius=300):
    """전주 주변에서 RANSAC affine fitting."""
    h, w = mvs.shape
    y0, y1 = max(0, py-radius), min(h, py+radius+1)
    x0, x1 = max(0, px-radius), min(w, px+radius+1)
    mvs_p = mvs[y0:y1, x0:x1]
    mde_p = mde[y0:y1, x0:x1]
    valid = (mvs_p > 0) & (mde_p > 0)
    m, d = mvs_p[valid], mde_p[valid]

    ransac = RANSACRegressor(estimator=LinearRegression(), min_samples=10,
                              residual_threshold=1.0, max_trials=1000)
    ransac.fit(d.reshape(-1, 1), m)
    return ransac.estimator_.coef_[0], ransac.estimator_.intercept_


def detect_wire_mask(mde, min_area=500, min_aspect_ratio=8.0, sobel_ksize=3,
                     binary_threshold=30, dilation_iterations=3):
    """MDE depth map에서 전선 형태 감지. Edge + contour + aspect ratio."""
    # Normalize to 8-bit
    mde_norm = cv2.normalize(mde.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    # Sobel edge
    grad_x = cv2.Sobel(mde_norm, cv2.CV_32F, 1, 0, ksize=sobel_ksize)
    grad_y = cv2.Sobel(mde_norm, cv2.CV_32F, 0, 1, ksize=sobel_ksize)
    grad = cv2.addWeighted(cv2.convertScaleAbs(grad_x), 1, cv2.convertScaleAbs(grad_y), 1, 0)

    # Binary + dilate
    _, binary = cv2.threshold(grad, binary_threshold, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=dilation_iterations)

    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    wire_mask = np.zeros(mde.shape, dtype=np.uint8)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        rect = cv2.minAreaRect(contour)
        w, h = rect[1]
        if w == 0 or h == 0:
            continue
        aspect = max(w, h) / min(w, h)
        if aspect < min_aspect_ratio:
            continue
        cv2.drawContours(wire_mask, [contour], -1, 255, thickness=cv2.FILLED)

    return wire_mask > 0


def create_point_cloud(depth, rgb, f_cam, cx, cy, crop=None, step=4):
    """Depth map → 3D point cloud."""
    if crop:
        x0, y0, x1, y1 = crop
        depth = depth[y0:y1, x0:x1]
        rgb = rgb[y0:y1, x0:x1]
        offset_x, offset_y = x0, y0
    else:
        offset_x, offset_y = 0, 0

    h, w = depth.shape
    ys, xs = np.mgrid[0:h:step, 0:w:step]
    ys, xs = ys.flatten(), xs.flatten()

    d = depth[ys, xs]
    valid = d > 0
    ys, xs, d = ys[valid], xs[valid], d[valid]

    x_3d = (xs + offset_x - cx) / f_cam * d
    y_3d = (ys + offset_y - cy) / f_cam * d
    z_3d = d
    colors = rgb[ys, xs]

    return np.column_stack([x_3d, y_3d, z_3d]), colors


def save_ply(path, points, colors):
    n = len(points)
    with open(path, 'w') as f:
        f.write(f'ply\nformat ascii 1.0\nelement vertex {n}\n')
        f.write('property float x\nproperty float y\nproperty float z\n')
        f.write('property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n')
        for i in range(n):
            f.write(f'{points[i,0]:.4f} {points[i,1]:.4f} {points[i,2]:.4f} '
                    f'{int(colors[i,0])} {int(colors[i,1])} {int(colors[i,2])}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mde', required=True)
    parser.add_argument('--mvs', required=True)
    parser.add_argument('--rgb', required=True)
    parser.add_argument('--pole_coords', nargs='+', required=True)
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--fit_radius', type=int, default=300)
    parser.add_argument('--depth_tolerance', type=float, default=5.0,
                        help='Pole depth ± tolerance for filling')
    parser.add_argument('--crop', default=None, help='Crop region x0,y0,x1,y1')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    base = os.path.basename(args.mde).replace('_depth.npy', '')

    poles = [(int(c.split(',')[0]), int(c.split(',')[1])) for c in args.pole_coords]

    mde = np.load(args.mde).astype(np.float64)
    mvs = np.array(Image.open(args.mvs)).astype(np.float64)
    rgb = np.array(Image.open(args.rgb))
    h, w = mde.shape
    f_cam, cx, cy = 8198.7, 4135, 2738

    print(f'Image: {w}x{h}, Poles: {len(poles)}')

    # Step 1: Fitting
    pole_depth_mean = 0
    for px, py in poles:
        r_c = 3
        center = mvs[max(0,py-r_c):min(h,py+r_c+1), max(0,px-r_c):min(w,px+r_c+1)]
        pole_depth_mean += np.median(center[center > 0])
    pole_depth_mean /= len(poles)

    scale, shift = fit_scale_shift(mvs, mde, poles[0][0], poles[0][1], args.fit_radius)
    print(f'Fitting: scale={scale:.4f}, shift={shift:.2f}')
    print(f'Pole depth: {pole_depth_mean:.2f}m')

    mde_cal = (scale * mde + shift).astype(np.float32)

    # Step 2: Wire detection (edge + aspect ratio)
    wire_mask = detect_wire_mask(mde)
    print(f'Wire mask: {np.sum(wire_mask)} pixels ({100*np.sum(wire_mask)/(h*w):.2f}%)')

    # Step 3: Depth range filter
    depth_range_mask = (np.abs(mde_cal - pole_depth_mean) <= args.depth_tolerance)

    # Step 4: Combined mask — MVS invalid + wire shape + depth range
    mvs_invalid = mvs <= 0
    fill_mask = mvs_invalid & wire_mask & depth_range_mask

    print(f'MVS invalid: {np.sum(mvs_invalid)} ({100*np.sum(mvs_invalid)/(h*w):.1f}%)')
    print(f'Wire + depth range: {np.sum(wire_mask & depth_range_mask)} pixels')
    print(f'Fill mask (invalid & wire & range): {np.sum(fill_mask)} pixels ({100*np.sum(fill_mask)/(h*w):.2f}%)')

    # Fuse
    fused = mvs.copy().astype(np.float32)
    fused[fill_mask] = mde_cal[fill_mask]

    np.save(os.path.join(args.output_dir, f'{base}_fused.npy'), fused)

    # 3D point cloud
    crop = None
    if args.crop:
        crop = tuple(int(x) for x in args.crop.split(','))

    # RGB colored
    pts, colors = create_point_cloud(fused, rgb, f_cam, cx, cy, crop=crop)
    save_ply(os.path.join(args.output_dir, f'{base}_fused.ply'), pts, colors)

    # Source colored (red=MDE filled, blue=MVS)
    source_rgb = rgb.copy()
    # Mark filled pixels in red
    fill_vis = np.zeros((h, w, 3), dtype=np.uint8)
    fill_vis[fill_mask] = [255, 50, 50]
    fill_vis[~fill_mask & (mvs > 0)] = [50, 50, 255]

    pts_src, colors_src = create_point_cloud(fused, fill_vis, f_cam, cx, cy, crop=crop)
    # Filter out pixels that have no source color (unfilled invalid)
    valid_src = np.any(colors_src > 0, axis=1)
    save_ply(os.path.join(args.output_dir, f'{base}_source.ply'),
             pts_src[valid_src], colors_src[valid_src])

    print(f'\nSaved:')
    print(f'  {base}_fused.npy')
    print(f'  {base}_fused.ply ({len(pts)} points)')
    print(f'  {base}_source.ply ({np.sum(valid_src)} points)')

    # Key values
    import json
    regions_path = 'scripts/region_selector/regions.json'
    if os.path.exists(regions_path):
        with open(regions_path) as f:
            all_regions = json.load(f)
        for entry in all_regions:
            if base.replace('_', '') not in entry.get('image', '').replace('_', ''):
                continue
            print(f'\n=== {entry["image"]} ===')
            regions = {k: v for k, v in entry.items() if k != 'image'}
            for name, pts_r in regions.items():
                for ox, oy in pts_r:
                    x, y = min(ox, w-1), min(oy, h-1)
                    f_val = fused[y, x]
                    m_val = mvs[y, x]
                    filled = fill_mask[y, x]
                    src = 'FILLED' if filled else ('MVS' if m_val > 0 else 'empty')
                    m_s = f'{m_val:.2f}' if m_val > 0 else '---'
                    print(f'  {name:>20s}: fused={f_val:.2f}m, MVS={m_s}, [{src}]')


if __name__ == '__main__':
    main()
