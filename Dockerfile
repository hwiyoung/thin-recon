# PatchFusion Docker environment for thin-recon pilot
# PyTorch 2.1 + CUDA 11.8 (PatchFusion requirement)

FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Clone PatchFusion
RUN git clone https://github.com/zhyever/PatchFusion.git

WORKDIR /workspace/PatchFusion

# Install mmengine/mmcv via openmim
RUN pip install --no-cache-dir openmim \
    && mim install mmengine "mmcv>=2.0.0"

# Install PatchFusion dependencies
RUN pip install --no-cache-dir \
    timm==0.9.2 \
    transformers==4.36.2 \
    huggingface-hub==0.20.1 \
    kornia==0.7.2 \
    scipy==1.10.1 \
    scikit-image==0.20.0 \
    einops==0.7.0 \
    opencv-python==4.8.1.78

# Install remaining requirements (ignore failures for already-installed)
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

# Set PYTHONPATH for PatchFusion + external deps (ZoeDepth, DepthAnything)
ENV PYTHONPATH="/workspace/PatchFusion:/workspace/PatchFusion/external:${PYTHONPATH}"

WORKDIR /workspace/PatchFusion
