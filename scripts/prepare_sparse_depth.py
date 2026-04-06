"""
COLMAP sparse points → per-image sparse depth map 변환.

COLMAP export (cameras.txt, images.txt, points3D.txt)에서
각 이미지에 projection된 sparse 3D points의 metric depth를
per-image depth map (.npy)으로 저장.

Prior Depth Anything의 prior input으로 사용.

Usage:
    python scripts/prepare_sparse_depth.py \
        --colmap_dir data/colmap_export \
        --output_dir data/sparse_depth_maps \
        --image_names DJI_20240424170547_0654.JPG DJI_20240424170551_0656.JPG
"""

import argparse
import os
import numpy as np


def parse_cameras(path):
    """cameras.txt → {cam_id: (model, width, height, params)}"""
    cameras = {}
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            cam_id = int(parts[0])
            model = parts[1]
            width, height = int(parts[2]), int(parts[3])
            params = [float(p) for p in parts[4:]]
            cameras[cam_id] = (model, width, height, params)
    return cameras


def parse_images(path):
    """images.txt → {name: (img_id, qvec, tvec, cam_id, points2d)}
    points2d = [(x, y, point3d_id), ...]
    """
    images = {}
    with open(path) as f:
        lines = [l.strip() for l in f if not l.startswith('#')]

    for i in range(0, len(lines), 2):
        parts = lines[i].split()
        img_id = int(parts[0])
        qvec = tuple(float(parts[j]) for j in range(1, 5))
        tvec = tuple(float(parts[j]) for j in range(5, 8))
        cam_id = int(parts[8])
        name = parts[9]

        pts_line = lines[i + 1].split()
        points2d = []
        for j in range(0, len(pts_line), 3):
            x, y = float(pts_line[j]), float(pts_line[j + 1])
            p3d_id = int(pts_line[j + 2])
            if p3d_id >= 0:
                points2d.append((x, y, p3d_id))

        images[name] = {
            'id': img_id,
            'qvec': qvec,
            'tvec': tvec,
            'cam_id': cam_id,
            'points2d': points2d,
        }
    return images


def parse_points3d(path):
    """points3D.txt → {point_id: (X, Y, Z)}"""
    points = {}
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            pid = int(parts[0])
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            points[pid] = (x, y, z)
    return points


def qvec2rotmat(qvec):
    """Quaternion (w, x, y, z) → 3x3 rotation matrix."""
    w, x, y, z = qvec
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
        [2*x*y + 2*w*z, 1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
        [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x*x - 2*y*y],
    ])


def compute_depth_from_3d(qvec, tvec, point3d_xyz):
    """3D world point → camera depth (z in camera frame)."""
    R = qvec2rotmat(qvec)
    t = np.array(tvec)
    p_cam = R @ np.array(point3d_xyz) + t
    return p_cam[2]  # depth = z in camera coordinates


def create_sparse_depth_map(image_data, points3d, cam_width, cam_height):
    """Create a sparse depth map for one image.

    Returns: (H, W) float32 array, NaN for invalid pixels.
    """
    depth_map = np.full((cam_height, cam_width), np.nan, dtype=np.float32)

    qvec = image_data['qvec']
    tvec = image_data['tvec']

    count = 0
    for x, y, p3d_id in image_data['points2d']:
        if p3d_id not in points3d:
            continue

        # Compute metric depth
        depth = compute_depth_from_3d(qvec, tvec, points3d[p3d_id])
        if depth <= 0:
            continue

        # Pixel coordinates (round to nearest)
        px, py = int(round(x)), int(round(y))
        if 0 <= px < cam_width and 0 <= py < cam_height:
            depth_map[py, px] = depth
            count += 1

    return depth_map, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--colmap_dir', required=True)
    parser.add_argument('--output_dir', required=True)
    parser.add_argument('--image_names', nargs='*', default=None,
                        help='Process only these images (default: all)')
    parser.add_argument('--add_dense_prior', default=None,
                        help='Directory of dense depth maps (.tif) to sample additional priors')
    parser.add_argument('--dense_sample_step', type=int, default=50,
                        help='Grid sampling step for dense depth (pixels)')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Parse COLMAP
    cameras = parse_cameras(os.path.join(args.colmap_dir, 'cameras.txt'))
    images = parse_images(os.path.join(args.colmap_dir, 'images.txt'))
    points3d = parse_points3d(os.path.join(args.colmap_dir, 'points3D.txt'))

    print(f'Cameras: {len(cameras)}, Images: {len(images)}, 3D Points: {len(points3d)}')

    # Get camera dimensions
    cam = list(cameras.values())[0]
    cam_model, cam_w, cam_h = cam[0], cam[1], cam[2]
    print(f'Camera: {cam_model}, {cam_w}x{cam_h}')

    # Filter images
    if args.image_names:
        target_names = set(args.image_names)
    else:
        target_names = None

    for img_name, img_data in images.items():
        # Match image name (Metashape may add _0 suffix)
        base = os.path.splitext(img_name)[0]
        original_name = None

        if target_names:
            for tn in target_names:
                tn_base = os.path.splitext(tn)[0]
                if tn_base in base:
                    original_name = tn
                    break
            if original_name is None:
                continue
        else:
            original_name = img_name

        out_base = os.path.splitext(original_name)[0]
        out_path = os.path.join(args.output_dir, f'{out_base}_sparse_depth.npy')

        # Create sparse depth map from COLMAP points
        depth_map, count = create_sparse_depth_map(img_data, points3d, cam_w, cam_h)
        print(f'{out_base}: {count} sparse points projected')

        # Optionally add dense prior samples
        if args.add_dense_prior:
            from PIL import Image
            dense_name = original_name.replace('.JPG', '.tif').replace('.jpg', '.tif')
            dense_path = os.path.join(args.add_dense_prior, dense_name)
            if os.path.exists(dense_path):
                dense_depth = np.array(Image.open(dense_path)).astype(np.float32)
                # Grid sample valid pixels
                step = args.dense_sample_step
                added = 0
                for y in range(0, dense_depth.shape[0], step):
                    for x in range(0, dense_depth.shape[1], step):
                        if dense_depth[y, x] > 0 and np.isnan(depth_map[min(y, cam_h-1), min(x, cam_w-1)]):
                            depth_map[min(y, cam_h-1), min(x, cam_w-1)] = dense_depth[y, x]
                            added += 1
                print(f'  + {added} dense prior samples (step={step})')

        np.save(out_path, depth_map)
        valid = np.sum(~np.isnan(depth_map))
        print(f'  Saved: {out_path} (valid: {valid})')


if __name__ == '__main__':
    main()
