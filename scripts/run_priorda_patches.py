"""
패치 기반 Prior DA 실행 + overlap blending.

1. 이미지를 1024×1024 overlapping patches로 분할
2. 각 패치에 해당하는 sparse prior 추출
3. Prior DA 실행 (패치별)
4. Overlap 영역에서 linear blending으로 합침
5. 최종 metric depth map 출력

Usage (in priorda container):
    python /scripts/run_priorda_patches.py \
        --image_path /data/images/DJI_20240424170551_0656.JPG \
        --prior_path /data/sparse_depth_maps/DJI_20240424170551_0656_sparse_depth.npy \
        --output_path /data/priorda_output/DJI_20240424170551_0656_patched.npy \
        --patch_size 1024 \
        --overlap 256
"""

import argparse
import os
import numpy as np
import torch
from PIL import Image
import time


def split_into_patches(h, w, patch_size, overlap):
    """Generate patch coordinates (y_start, x_start) with overlap."""
    stride = patch_size - overlap
    patches = []
    for y in range(0, h, stride):
        for x in range(0, w, stride):
            y_end = min(y + patch_size, h)
            x_end = min(x + patch_size, w)
            y_start = y_end - patch_size  # ensure full patch_size
            x_start = x_end - patch_size
            y_start = max(0, y_start)
            x_start = max(0, x_start)
            patches.append((y_start, x_start, y_end, x_end))
    # Remove duplicates
    patches = list(set(patches))
    patches.sort()
    return patches


def create_blend_weights(h, w, overlap):
    """Create linear blending weights — ramp up at edges within overlap region."""
    weights = np.ones((h, w), dtype=np.float32)
    if overlap <= 0:
        return weights

    ramp = np.linspace(0, 1, overlap)

    # Top edge
    for i in range(min(overlap, h)):
        weights[i, :] *= ramp[i]
    # Bottom edge
    for i in range(min(overlap, h)):
        weights[h - 1 - i, :] *= ramp[i]
    # Left edge
    for j in range(min(overlap, w)):
        weights[:, j] *= ramp[j]
    # Right edge
    for j in range(min(overlap, w)):
        weights[:, w - 1 - j] *= ramp[j]

    return weights


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_path', required=True)
    parser.add_argument('--prior_path', required=True, help='Sparse depth map (.npy)')
    parser.add_argument('--output_path', required=True)
    parser.add_argument('--patch_size', type=int, default=1024)
    parser.add_argument('--overlap', type=int, default=256)
    parser.add_argument('--device', default='cuda:0')
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output_path) or '.', exist_ok=True)

    # Load full image
    img_full = np.array(Image.open(args.image_path))
    h, w = img_full.shape[:2]
    print(f'Image: {w}x{h}')

    # Load sparse prior (may be different resolution from image)
    prior_full = np.load(args.prior_path)
    prior_h, prior_w = prior_full.shape
    print(f'Prior: {prior_w}x{prior_h}, valid: {np.sum(~np.isnan(prior_full))}')

    # Scale factor between prior and image
    sy = h / prior_h
    sx = w / prior_w
    print(f'Scale factor: sx={sx:.3f}, sy={sy:.3f}')

    # Generate patches
    patches = split_into_patches(h, w, args.patch_size, args.overlap)
    print(f'Patches: {len(patches)} ({args.patch_size}x{args.patch_size}, overlap={args.overlap})')

    # Load Prior DA
    from prior_depth_anything import PriorDepthAnything
    print('Loading Prior DA...')
    priorda = PriorDepthAnything(device=args.device)
    print('Model loaded.')

    # Output accumulator
    depth_accum = np.zeros((h, w), dtype=np.float64)
    weight_accum = np.zeros((h, w), dtype=np.float64)

    # Blend weights for a full patch
    blend_w = create_blend_weights(args.patch_size, args.patch_size, args.overlap)

    t_start = time.time()

    for idx, (y0, x0, y1, x1) in enumerate(patches):
        ph, pw = y1 - y0, x1 - x0

        # Extract image patch
        img_patch = img_full[y0:y1, x0:x1]

        # Extract prior patch (convert coords to prior space)
        py0, px0 = int(y0 / sy), int(x0 / sx)
        py1, px1 = int(y1 / sy), int(x1 / sx)
        py1 = min(py1, prior_h)
        px1 = min(px1, prior_w)
        prior_patch = prior_full[py0:py1, px0:px1]

        # Resize prior patch to match image patch size
        from PIL import Image as PILImage
        if prior_patch.shape[0] != ph or prior_patch.shape[1] != pw:
            # Use nearest for sparse data to avoid interpolation artifacts
            prior_resized = np.full((ph, pw), np.nan, dtype=np.float32)
            for y in range(prior_patch.shape[0]):
                for x in range(prior_patch.shape[1]):
                    if not np.isnan(prior_patch[y, x]):
                        ty = int(y * sy)
                        tx = int(x * sx)
                        if 0 <= ty < ph and 0 <= tx < pw:
                            prior_resized[ty, tx] = prior_patch[y, x]
            prior_patch = prior_resized

        valid_count = np.sum(~np.isnan(prior_patch))
        if valid_count < 10:
            print(f'  [{idx+1}/{len(patches)}] ({x0},{y0})-({x1},{y1}): skip (only {valid_count} prior points)')
            continue

        # Save temp files
        PILImage.fromarray(img_patch).save('/tmp/patch_img.jpg')
        np.save('/tmp/patch_prior.npy', prior_patch.astype(np.float32))

        # Run Prior DA
        try:
            output = priorda.infer_one_sample(
                image='/tmp/patch_img.jpg',
                prior='/tmp/patch_prior.npy',
                visualize=False
            )

            if isinstance(output, torch.Tensor):
                depth_patch = output.squeeze().detach().cpu().numpy()
            elif isinstance(output, dict):
                depth_patch = list(output.values())[0]
                if isinstance(depth_patch, torch.Tensor):
                    depth_patch = depth_patch.squeeze().detach().cpu().numpy()
            else:
                depth_patch = np.array(output).squeeze()

            depth_patch = depth_patch.astype(np.float64)

            # Resize to patch dimensions if needed
            if depth_patch.shape != (ph, pw):
                depth_patch = np.array(
                    PILImage.fromarray(depth_patch.astype(np.float32)).resize((pw, ph), PILImage.BILINEAR)
                ).astype(np.float64)

            # Apply blend weights
            bw = blend_w[:ph, :pw]
            depth_accum[y0:y1, x0:x1] += depth_patch * bw
            weight_accum[y0:y1, x0:x1] += bw

            elapsed = time.time() - t_start
            avg = elapsed / (idx + 1)
            remaining = avg * (len(patches) - idx - 1)
            print(f'  [{idx+1}/{len(patches)}] ({x0},{y0}): range=[{depth_patch.min():.1f}, {depth_patch.max():.1f}] '
                  f'prior={valid_count} ({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)')

        except Exception as e:
            print(f'  [{idx+1}/{len(patches)}] ({x0},{y0}): ERROR {e}')
            torch.cuda.empty_cache()

    # Normalize by weights
    valid_mask = weight_accum > 0
    depth_final = np.zeros((h, w), dtype=np.float32)
    depth_final[valid_mask] = (depth_accum[valid_mask] / weight_accum[valid_mask]).astype(np.float32)

    np.save(args.output_path, depth_final)
    total_time = time.time() - t_start
    print(f'\nDone. Shape: {depth_final.shape}, range: [{depth_final[valid_mask].min():.2f}, {depth_final[valid_mask].max():.2f}]')
    print(f'Total time: {total_time:.0f}s')
    print(f'Saved: {args.output_path}')


if __name__ == '__main__':
    main()
