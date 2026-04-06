"""
Prior Depth Anything 실행 스크립트.

Sparse depth map (from prepare_sparse_depth.py) + RGB image →
Prior DA로 metric depth map 생성.

Usage (in priorda container):
    python /scripts/run_priorda.py \
        --image_dir /data/images \
        --prior_dir /data/sparse_depth_maps \
        --output_dir /data/priorda_output \
        --image_names DJI_20240424170547_0654.JPG

해상도 참고:
    Prior DA는 518x518로 학습됨. 8192x5460 이미지는 내부적으로
    리사이즈되어 처리 후 원본 크기로 업스케일됨.
"""

import argparse
import os
import glob
import numpy as np
import torch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_dir', required=True)
    parser.add_argument('--prior_dir', required=True,
                        help='Directory of sparse depth maps (.npy)')
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--image_names', nargs='*', default=None)
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--coarse_only', action='store_true',
                        help='Use coarse alignment only (faster)')
    parser.add_argument('--downscale', type=int, default=None,
                        help='Downscale factor for input (e.g., 4 for 2048x1365)')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load Prior DA
    from prior_depth_anything import PriorDepthAnything

    print(f'Loading Prior Depth Anything (coarse_only={args.coarse_only})...')
    priorda = PriorDepthAnything(
        device=args.device,
        coarse_only=args.coarse_only
    )
    print('Model loaded.')

    # Find images
    if args.image_names:
        image_files = [os.path.join(args.image_dir, n) for n in args.image_names]
    else:
        image_files = sorted(
            glob.glob(os.path.join(args.image_dir, '*.JPG')) +
            glob.glob(os.path.join(args.image_dir, '*.jpg'))
        )

    for img_path in image_files:
        name = os.path.splitext(os.path.basename(img_path))[0]
        prior_path = os.path.join(args.prior_dir, f'{name}_sparse_depth.npy')
        out_path = os.path.join(args.output_dir, f'{name}_metric_depth.npy')

        if not os.path.exists(prior_path):
            print(f'[SKIP] {name}: no sparse depth map at {prior_path}')
            continue

        if os.path.exists(out_path):
            print(f'[SKIP] {name}: already processed')
            continue

        print(f'\nProcessing: {name}')

        # Load and optionally downscale
        from PIL import Image
        import cv2

        img = Image.open(img_path)
        prior = np.load(prior_path)

        if args.downscale and args.downscale > 1:
            s = args.downscale
            orig_size = img.size  # (W, H)
            new_w, new_h = orig_size[0] // s, orig_size[1] // s
            img = img.resize((new_w, new_h), Image.LANCZOS)

            # Downscale prior depth map
            prior_ds = np.full((new_h, new_w), np.nan, dtype=np.float32)
            for y in range(new_h):
                for x in range(new_w):
                    patch = prior[y*s:(y+1)*s, x*s:(x+1)*s]
                    valid = patch[~np.isnan(patch)]
                    if len(valid) > 0:
                        prior_ds[y, x] = np.mean(valid)
            prior = prior_ds
            print(f'  Downscaled: {orig_size} → ({new_w}, {new_h})')

        # Save temp files for Prior DA
        tmp_img = '/tmp/priorda_input_img.jpg'
        tmp_prior = '/tmp/priorda_input_prior.npy'
        img.save(tmp_img)
        np.save(tmp_prior, prior)

        # Run Prior DA
        try:
            output = priorda.infer_one_sample(
                image=tmp_img,
                prior=tmp_prior,
                visualize=False
            )

            # Extract depth from output
            if isinstance(output, dict):
                depth = output.get('depth', output.get('metric_depth', None))
                if depth is None:
                    depth = list(output.values())[0]
            elif isinstance(output, torch.Tensor):
                depth = output
            else:
                depth = output

            if isinstance(depth, torch.Tensor):
                depth = depth.detach().cpu().numpy()

            depth = depth.squeeze().astype(np.float32)
            print(f'  Output shape: {depth.shape}, range: [{depth.min():.2f}, {depth.max():.2f}]')

            np.save(out_path, depth)
            print(f'  Saved: {out_path}')

        except Exception as e:
            print(f'  [ERROR] {e}')
            torch.cuda.empty_cache()

    print('\nDone.')


if __name__ == '__main__':
    main()
