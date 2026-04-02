"""
Patch PatchFusion's __init__ to fix nested dict attribute access issue.
PretrainedConfig doesn't recursively convert nested dicts.
Fix: use mmengine ConfigDict for the else branch (HF loading).
"""

PATCH_FILE = "/workspace/PatchFusion/estimator/models/patchfusion.py"

with open(PATCH_FILE, "r") as f:
    code = f.read()

# Replace the else branch that handles HuggingFace loading
old = """        else:
            # NOTE:
            # used when loading patchfusion from hf model space (inference with network in readme)
            # PretrainedConfig.from_dict(**config) will raise an error (dict is saved as str in this case)
            # we use MMengine ConfigDict to convert str to dict correctly here
            config = PretrainedConfig.from_dict(ConfigDict(**config).to_dict())
            config.load_branch = False
            config.coarse_branch.pretrained_resource = None
            config.fine_branch.pretrained_resource = None"""

new = """        else:
            # NOTE: Use ConfigDict directly for recursive attribute access
            config = ConfigDict(**config)
            config.load_branch = False
            config.coarse_branch.pretrained_resource = None
            config.fine_branch.pretrained_resource = None"""

if old in code:
    code = code.replace(old, new)
    with open(PATCH_FILE, "w") as f:
        f.write(code)
    print("Patched patchfusion.py successfully")
else:
    print("WARNING: Patch target not found — code may have changed")
    print("Attempting fallback patch...")
    # Try to find and replace just the problematic line
    if "PretrainedConfig.from_dict(ConfigDict(**config).to_dict())" in code:
        code = code.replace(
            "config = PretrainedConfig.from_dict(ConfigDict(**config).to_dict())",
            "config = ConfigDict(**config)"
        )
        with open(PATCH_FILE, "w") as f:
            f.write(code)
        print("Fallback patch applied")
    else:
        print("Could not find patch target")
