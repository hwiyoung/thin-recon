"""
Step 1: PatchFusion 고해상도 relative depth estimation.

8192x5460 드론 이미지를 패치 기반으로 처리하여
전선이 보존된 고해상도 depth map 생성.

Usage (in patchfusion container):
    python /scripts/run_patchfusion.py \
        --input_dir /data/images \
        --output_dir /data/depth_output

    # 1장만 테스트:
    python /scripts/run_patchfusion.py \
        --input_dir /data/images \
        --output_dir /data/depth_output \
        --max_images 1
"""

import argparse
import glob
import os
import sys
import time

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms


def run_patchfusion(image_path, model, device='cuda', cai_mode='r128', process_num=2):
    """
    PatchFusion으로 단일 이미지의 고해상도 relative depth 추정.
    Returns: depth (H, W) float32 numpy array
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Cannot read: {image_path}")
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) / 255.0
    image = transforms.ToTensor()(np.asarray(image)).float()

    h, w = image.shape[1], image.shape[2]
    print(f"  Image size: {w}x{h}")

    # image_raw_shape must satisfy: dim % (2 * patch_split_num) == 0
    # For 8192x5460: patch_split_num=[7,8] → 5460/14=390, 8192/16=512 ✓
    # For other sizes, use model defaults
    if h == 5460 and w == 8192:
        image_raw_shape = [5460, 8192]
        patch_split_num = [7, 8]
    else:
        # Find valid patch_split_num for arbitrary sizes
        # Use reasonable defaults that satisfy divisibility
        ps_h = 4
        ps_w = 4
        # Adjust to satisfy constraint: dim % (2*ps) == 0
        while h % (2 * ps_h) != 0 and ps_h > 1:
            ps_h -= 1
        while w % (2 * ps_w) != 0 and ps_w > 1:
            ps_w -= 1
        image_raw_shape = [h, w]
        patch_split_num = [ps_h, ps_w]

    print(f"  image_raw_shape: {image_raw_shape}")
    print(f"  patch_split_num: {patch_split_num}")

    # Prepare low-res and high-res inputs
    image_resizer = model.resizer
    image_lr = image_resizer(image.unsqueeze(dim=0)).float().to(device)
    image_hr = F.interpolate(
        image.unsqueeze(dim=0),
        image_raw_shape,
        mode='bicubic',
        align_corners=True
    ).float().to(device)

    tile_cfg = {
        'image_raw_shape': image_raw_shape,
        'patch_split_num': patch_split_num,
    }

    with torch.no_grad():
        depth_prediction, _ = model(
            mode='infer',
            cai_mode=cai_mode,
            process_num=process_num,
            image_lr=image_lr,
            image_hr=image_hr,
            tile_cfg=tile_cfg,
        )

    # Resize to original resolution
    depth_prediction = F.interpolate(
        depth_prediction, (h, w), mode='bicubic', align_corners=True
    )
    depth = depth_prediction.squeeze().cpu().numpy()

    return depth.astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description="PatchFusion high-res depth estimation")
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_name", default="Zhyever/patchfusion_depth_anything_vitl14")
    parser.add_argument("--mode", default="r128", help="CAI mode: r64, r128, r256")
    parser.add_argument("--process_num", type=int, default=2, help="Patch batch size (lower if OOM)")
    parser.add_argument("--max_images", type=int, default=0, help="Max images to process (0=all)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load model
    print(f"Loading PatchFusion model: {args.model_name}")
    try:
        from estimator.models.patchfusion import PatchFusion
        model = PatchFusion.from_pretrained(args.model_name).to('cuda').eval()
    except ImportError as e:
        print(f"[ERROR] Cannot import PatchFusion: {e}")
        print("Make sure PYTHONPATH includes /workspace/PatchFusion and /workspace/PatchFusion/external")
        sys.exit(1)
    print("Model loaded.")

    # Find images
    images = sorted(
        glob.glob(os.path.join(args.input_dir, "*.JPG")) +
        glob.glob(os.path.join(args.input_dir, "*.jpg")) +
        glob.glob(os.path.join(args.input_dir, "*.png"))
    )
    if args.max_images > 0:
        images = images[:args.max_images]
    print(f"Processing {len(images)} images")

    # Skip already processed
    for i, img_path in enumerate(images):
        name = os.path.splitext(os.path.basename(img_path))[0]
        out_path = os.path.join(args.output_dir, f"{name}_depth.npy")

        if os.path.exists(out_path):
            print(f"\n[{i+1}/{len(images)}] {name} — already exists, skipping")
            continue

        print(f"\n[{i+1}/{len(images)}] Processing: {name}")
        t0 = time.time()

        try:
            depth = run_patchfusion(
                img_path, model,
                cai_mode=args.mode,
                process_num=args.process_num
            )
            np.save(out_path, depth)
            elapsed = time.time() - t0
            print(f"  Shape: {depth.shape}, range: [{depth.min():.4f}, {depth.max():.4f}]")
            print(f"  Saved: {out_path} ({elapsed:.1f}s)")
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"  [OOM] GPU memory 부족. --process_num을 줄이거나 --mode를 r64로 변경하세요.")
                torch.cuda.empty_cache()
            else:
                raise

    print("\nDone.")


if __name__ == "__main__":
    main()
