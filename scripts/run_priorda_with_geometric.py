"""
Prior DA + PatchFusion geometric input.

PatchFusion의 고해상도 relative depth를 geometric으로 제공하여
Prior DA가 DA V2 대신 PatchFusion의 구조(전선 포함)를 사용하도록 함.
"""
import argparse
import os
import numpy as np
import torch
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_dir', required=True)
    parser.add_argument('--prior_dir', required=True, help='Sparse depth maps (.npy)')
    parser.add_argument('--patchfusion_dir', required=True, help='PatchFusion depth maps (.npy)')
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--image_names', nargs='+', required=True)
    parser.add_argument('--downscale', type=int, default=4)
    parser.add_argument('--device', default='cuda:0')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    s = args.downscale

    from prior_depth_anything import PriorDepthAnything

    print(f'Loading Prior DA...')
    priorda = PriorDepthAnything(device=args.device)
    print('Model loaded.')

    for image_name in args.image_names:
        base = os.path.splitext(image_name)[0]
        out_path = os.path.join(args.output_dir, f'{base}_metric_depth_geo.npy')

        print(f'\nProcessing: {base}')

        # Load original image and downscale
        img = Image.open(os.path.join(args.image_dir, image_name))
        orig_w, orig_h = img.size
        new_w, new_h = orig_w // s, orig_h // s
        img_ds = img.resize((new_w, new_h), Image.LANCZOS)
        img_ds.save('/tmp/priorda_img.jpg')
        print(f'  Image: {orig_w}x{orig_h} -> {new_w}x{new_h}')

        # Load and downscale sparse prior
        prior = np.load(os.path.join(args.prior_dir, f'{base}_sparse_depth.npy'))
        prior_ds = np.full((new_h, new_w), np.nan, dtype=np.float32)
        for y in range(new_h):
            for x in range(new_w):
                patch = prior[y*s:(y+1)*s, x*s:(x+1)*s]
                valid = patch[~np.isnan(patch)]
                if len(valid) > 0:
                    prior_ds[y, x] = np.mean(valid)
        np.save('/tmp/priorda_prior.npy', prior_ds)
        valid_count = np.sum(~np.isnan(prior_ds))
        print(f'  Prior: {valid_count} valid points')

        # Load and downscale PatchFusion depth (geometric input)
        pf_depth = np.load(os.path.join(args.patchfusion_dir, f'{base}_depth.npy'))
        pf_ds = np.array(Image.fromarray(pf_depth).resize((new_w, new_h), Image.BILINEAR))
        np.save('/tmp/priorda_geo.npy', pf_ds.astype(np.float32))
        print(f'  PatchFusion geometric: range [{pf_ds.min():.2f}, {pf_ds.max():.2f}]')

        # Run Prior DA with geometric input
        try:
            output = priorda.infer_one_sample(
                image='/tmp/priorda_img.jpg',
                prior='/tmp/priorda_prior.npy',
                geometric='/tmp/priorda_geo.npy',
                visualize=False
            )

            if isinstance(output, torch.Tensor):
                depth = output.squeeze().detach().cpu().numpy()
            elif isinstance(output, dict):
                depth = list(output.values())[0]
                if isinstance(depth, torch.Tensor):
                    depth = depth.squeeze().detach().cpu().numpy()
            else:
                depth = np.array(output).squeeze()

            depth = depth.astype(np.float32)
            np.save(out_path, depth)
            print(f'  Output: shape={depth.shape}, range=[{depth.min():.2f}, {depth.max():.2f}]')
            print(f'  Saved: {out_path}')

            # Quick check at key locations
            pts = {
                'pole_top': (6620, 2715),
                'wire_center': (4734, 2935),
                'background': (4366, 2492),
            }
            for name, (ox, oy) in pts.items():
                x, y = min(ox // s, depth.shape[1]-1), min(oy // s, depth.shape[0]-1)
                print(f'  {name:20s}: {depth[y, x]:.2f}m')

        except Exception as e:
            print(f'  [ERROR] {e}')
            import traceback
            traceback.print_exc()
            torch.cuda.empty_cache()

    print('\nDone.')


if __name__ == '__main__':
    main()
