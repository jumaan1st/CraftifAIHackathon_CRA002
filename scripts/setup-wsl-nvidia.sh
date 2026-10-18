#!/usr/bin/env bash
set -euo pipefail
# Official NVIDIA apt repository; configure only the dedicated SmartGate WSL Docker engine.
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o /tmp/nvidia-container.gpg
gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg /tmp/nvidia-container.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list -o /tmp/nvidia-container.list
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' /tmp/nvidia-container.list > /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
docker version
