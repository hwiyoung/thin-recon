"""
Prior DA의 내부 해상도를 518 → 1022로 변경하는 패치.
thin structure(전선)가 518에서 소실되는 문제를 해결.
1022 = 73 * 14 (ViT patch size 14의 배수)
"""
import sys

PATCH_FILE = "/workspace/Prior-Depth-Anything/prior_depth_anything/depth_completion.py"
TARGET_SIZE = sys.argv[1] if len(sys.argv) > 1 else "1022"

with open(PATCH_FILE, "r") as f:
    code = f.read()

old = "            heit = 518"
new = f"            heit = {TARGET_SIZE}  # patched for thin structure preservation (was 518)"

if old in code:
    code = code.replace(old, new)
    with open(PATCH_FILE, "w") as f:
        f.write(code)
    print(f"Patched depth_completion.py: heit = {TARGET_SIZE}")
elif f"heit = {TARGET_SIZE}" in code:
    print(f"Already patched to {TARGET_SIZE}")
else:
    print("WARNING: patch target not found")
    sys.exit(1)
