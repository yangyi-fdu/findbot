#!/usr/bin/env bash
# Python packages that are not in the ROS apt repositories, in a venv:
#   PyTorch (CPU), Ultralytics YOLO, and the LLM SDKs (Zhipu zai-sdk, Anthropic).
# --system-site-packages keeps rclpy / cv_bridge importable; numpy<2 because cv_bridge
# was built against numpy 1.x. Only the nodes that need these add the venv to their path.
set -e
V=~/findbot_venv
[ -d $V ] || python3 -m venv --system-site-packages $V
source $V/bin/activate
pip install -q --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics zai-sdk anthropic "numpy<2" "opencv-python-headless<4.11"
python -c "import torch, ultralytics, zai, anthropic, numpy; print('ok: numpy', numpy.__version__)"
echo "Next: bash scripts/download_models.sh"
