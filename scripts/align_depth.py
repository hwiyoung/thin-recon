"""
MVS dense depth + PatchFusion relative depth → metric depth (직접 alignment).

MVS valid pixel 중 관심 depth range 내의 pixel에서
PatchFusion relative depth와 MVS metric depth 간 affine 관계를 fitting하고,
PatchFusion 전체에 적용하여 전선 포함 metric depth를 생성.

Usage:
    python scripts/align_depth.py \
        --patchfusion data/depth_output/DJI_xxx_depth.npy \
        --mvs /path/to/depthmaps/DJI_xxx.tif \
        --output data/aligned_output/DJI_xxx_aligned.npy \
        --depth_min 55 --depth_max 85
"""

import argparse
import os
import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--patchfusion', required=True, help='PatchFusion relative depth (.npy)')
    parser.add_argument('--mvs', required=True, help='MVS dense depth (.tif)')
    parser.add_argument('--output', required=True, help='Output aligned metric depth (.npy)')
    parser.add_argument('--depth_min', type=float, default=55.0, help='Min depth for fitting (m)')
    parser.add_argument('--depth_max', type=float, default=85.0, help='Max depth for fitting (m)')
    parser.add_argument('--sample_step', type=int, default=1, help='Sampling step (1=all, 10=every 10th pixel)')
    parser.add_argument('--grid_size', type=int, default=512, help='Grid cell size for local fitting (pixels)')
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)

    # Load
    pf = np.load(args.patchfusion).astype(np.float64)
    mvs = np.array(Image.open(args.mvs)).astype(np.float64)

    print(f'PatchFusion: {pf.shape}, range=[{pf.min():.2f}, {pf.max():.2f}]')
    print(f'MVS: {mvs.shape}, range=[{mvs[mvs>0].min():.2f}, {mvs[mvs>0].max():.2f}]')

    # Resize if shapes differ
    if pf.shape != mvs.shape:
        print(f'Resizing MVS {mvs.shape} → PatchFusion {pf.shape}')
        mvs = np.array(Image.fromarray(mvs).resize(
            (pf.shape[1], pf.shape[0]), Image.NEAREST
        )).astype(np.float64)

    # Build mask: MVS valid + within depth range
    mask = (mvs > 0) & (mvs >= args.depth_min) & (mvs <= args.depth_max) & np.isfinite(pf) & (pf > 0)

    # Optional subsampling for speed
    if args.sample_step > 1:
        sparse_mask = np.zeros_like(mask)
        sparse_mask[::args.sample_step, ::args.sample_step] = True
        mask = mask & sparse_mask

    n_points = np.sum(mask)
    print(f'Fitting points: {n_points} (depth range [{args.depth_min}, {args.depth_max}]m)')

    if n_points < 100:
        print('[ERROR] Not enough points for fitting')
        return

    pf_vals = pf[mask]
    mvs_vals = mvs[mask]

    # Local affine fitting: 이미지를 grid로 나눠서 local scale/shift fitting
    grid_size = args.grid_size
    h, w = pf.shape
    gh = (h + grid_size - 1) // grid_size
    gw = (w + grid_size - 1) // grid_size
    print(f'Local fitting: {gw}x{gh} grid (cell={grid_size}px)')

    scale_map = np.full((gh, gw), np.nan, dtype=np.float64)
    shift_map = np.full((gh, gw), np.nan, dtype=np.float64)

    for gy in range(gh):
        for gx in range(gw):
            y0g = gy * grid_size
            x0g = gx * grid_size
            y1g = min(y0g + grid_size, h)
            x1g = min(x0g + grid_size, w)

            cell_mask = mask[y0g:y1g, x0g:x1g]
            if np.sum(cell_mask) < 50:
                continue

            pf_cell = pf[y0g:y1g, x0g:x1g][cell_mask]
            mvs_cell = mvs[y0g:y1g, x0g:x1g][cell_mask]

            A_cell = np.vstack([pf_cell, np.ones(len(pf_cell))]).T
            result = np.linalg.lstsq(A_cell, mvs_cell, rcond=None)
            scale_map[gy, gx] = result[0][0]
            shift_map[gy, gx] = result[0][1]

    # Fill NaN cells with nearest valid
    from scipy.ndimage import distance_transform_edt
    nan_mask = np.isnan(scale_map)
    if np.any(nan_mask) and not np.all(nan_mask):
        # Nearest neighbor fill
        _, nearest_idx = distance_transform_edt(nan_mask, return_distances=True, return_indices=True)
        scale_map = scale_map[tuple(nearest_idx)]
        shift_map = shift_map[tuple(nearest_idx)]

    valid_cells = np.sum(~np.isnan(scale_map))
    print(f'Valid cells: {valid_cells}/{gh*gw}')
    print(f'Scale range: [{np.nanmin(scale_map):.4f}, {np.nanmax(scale_map):.4f}]')
    print(f'Shift range: [{np.nanmin(shift_map):.2f}, {np.nanmax(shift_map):.2f}]')

    # Interpolate scale/shift to full resolution (bilinear)
    from scipy.ndimage import zoom
    # Grid center coordinates
    scale_full = zoom(scale_map, (h / gh, w / gw), order=1)[:h, :w]
    shift_full = zoom(shift_map, (h / gh, w / gw), order=1)[:h, :w]

    # Apply local affine
    aligned = (scale_full * pf + shift_full).astype(np.float32)

    # Residual statistics on fitting pixels
    predicted = aligned[mask[:h, :w]]
    actual = mvs[mask[:h, :w]]
    residuals = actual - predicted
    print(f'Residuals: MAE={np.mean(np.abs(residuals)):.3f}m, '
          f'RMSE={np.sqrt(np.mean(residuals**2)):.3f}m, '
          f'max={np.max(np.abs(residuals)):.3f}m')

    print(f'Aligned: range=[{aligned.min():.2f}, {aligned.max():.2f}]')

    np.save(args.output, aligned)
    print(f'Saved: {args.output}')

    # Report key points if regions.json exists
    import json
    regions_path = 'scripts/region_selector/regions.json'
    if os.path.exists(regions_path):
        with open(regions_path) as f:
            all_regions = json.load(f)

        basename = os.path.basename(args.patchfusion).replace('_depth.npy', '.JPG')
        for entry in all_regions:
            if basename not in entry.get('image', ''):
                continue

            print(f'\n=== {entry["image"]} ===')
            print(f'{"Region":>20s} {"Aligned":>9s} {"MVS":>9s} {"PF(rel)":>9s}')
            print('-' * 52)

            regions = {k: v for k, v in entry.items() if k != 'image'}
            for name, pts in regions.items():
                for ox, oy in pts:
                    x = min(ox, aligned.shape[1]-1)
                    y = min(oy, aligned.shape[0]-1)
                    al = aligned[y, x]
                    mv = mvs[y, x] if mvs[y, x] > 0 else float('nan')
                    pv = pf[y, x]
                    mv_s = f'{mv:.2f}' if mv > 0 else '---'
                    print(f'{name:>20s} {al:9.2f} {mv_s:>9s} {pv:9.4f}')

                if 'wire' in name:
                    for ox, oy in pts:
                        x, y = min(ox, aligned.shape[1]-1), min(oy, aligned.shape[0]-1)
                        patch = aligned[max(0,y-8):min(aligned.shape[0],y+9),
                                        max(0,x-8):min(aligned.shape[1],x+9)]
                        print(f'{name+" (min)":>20s} {patch.min():9.2f}')

            # Vertical profile
            wire_pts = entry.get('wire_center', [])
            if wire_pts:
                ox, oy = wire_pts[0]
                x, y = min(ox, aligned.shape[1]-1), min(oy, aligned.shape[0]-1)
                print(f'\nVertical profile at wire_center ({ox},{oy}):')
                for dy in range(-10, 11, 2):
                    yy = y + dy
                    if 0 <= yy < aligned.shape[0]:
                        al = aligned[yy, x]
                        mv = mvs[yy, x]
                        mv_s = f'{mv:.2f}' if mv > 0 else '---'
                        marker = ' <<<' if dy == 0 else ''
                        print(f'  y={yy}: aligned={al:.2f}  MVS={mv_s}{marker}')


if __name__ == '__main__':
    main()
