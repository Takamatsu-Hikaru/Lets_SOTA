"""
硬件检测模块
自动探测 CPU/GPU 能力，生成硬件指纹，推荐训练参数
"""

import platform
import hashlib
import math
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class HardwareProfile:
    """玩家硬件档案"""
    # CPU
    cpu_name: str
    cpu_cores: int
    cpu_threads: int
    ram_gb: float

    # GPU
    has_gpu: bool
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    gpu_compute_capability: Optional[str] = None
    cuda_version: Optional[str] = None

    # 分类标签（用于排行榜分组）
    tier: str = "cpu"  # cpu / gpu-low / gpu-mid / gpu-high

    # 硬件指纹（匿名化）
    fingerprint: str = ""

    def __post_init__(self):
        self.fingerprint = self._make_fingerprint()
        self.tier = self._classify_tier()

    def _make_fingerprint(self) -> str:
        """生成硬件指纹，用于识别同一台机器"""
        raw = f"{self.cpu_name}_{self.cpu_cores}_{self.ram_gb}_{self.gpu_name}_{self.gpu_vram_gb}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _classify_tier(self) -> str:
        """
        硬件分级：
        - cpu: 无 GPU 或 VRAM < 2GB
        - gpu-low: VRAM 2-6GB (GTX 1050, MX 系列等)
        - gpu-mid: VRAM 6-12GB (RTX 3060, RTX 4060 等)
        - gpu-high: VRAM 12GB+ (RTX 3090, RTX 4090, A100 等)
        """
        if not self.has_gpu or self.gpu_vram_gb is None:
            return "cpu"
        if self.gpu_vram_gb < 2:
            return "cpu"
        if self.gpu_vram_gb < 6:
            return "gpu-low"
        if self.gpu_vram_gb < 12:
            return "gpu-mid"
        return "gpu-high"


def detect_hardware() -> HardwareProfile:
    """检测当前机器硬件"""
    import psutil
    import torch

    # CPU 信息
    cpu_name = platform.processor() or "Unknown CPU"
    # 尝试从 /proc/cpuinfo 获取更好的名称
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_name = line.split(":")[1].strip()
                    break
    except (FileNotFoundError, PermissionError):
        pass

    cpu_cores = psutil.cpu_count(logical=False) or 1
    cpu_threads = psutil.cpu_count(logical=True) or 1
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)

    # GPU 信息
    has_gpu = torch.cuda.is_available()
    gpu_name = None
    gpu_vram_gb = None
    gpu_cc = None
    cuda_ver = None

    if has_gpu:
        gpu_name = torch.cuda.get_device_name(0)
        gpu_vram_gb = round(torch.cuda.get_device_properties(0).total_mem / (1024 ** 3), 1)
        cc = torch.cuda.get_device_capability(0)
        gpu_cc = f"{cc[0]}.{cc[1]}"
        cuda_ver = torch.version.cuda

    return HardwareProfile(
        cpu_name=cpu_name,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        ram_gb=ram_gb,
        has_gpu=has_gpu,
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram_gb,
        gpu_compute_capability=gpu_cc,
        cuda_version=cuda_ver,
    )


def recommend_batch_size(profile: HardwareProfile, dataset: str) -> int:
    """
    根据硬件和数据集推荐 batch size
    目标：不 OOM + 合理利用显存/内存
    """
    # 每张图预估显存占用 (MB)
    dataset_mem_map = {
        "mnist": 0.003,         # 28x28x1 很小
        "fashion-mnist": 0.003,
        "cifar10": 0.012,       # 32x32x3
        "cifar100": 0.012,
        "imagenet-tiny": 0.6,   # 64x64x3 + 增强
    }
    per_sample_mb = dataset_mem_map.get(dataset, 0.01)

    if profile.has_gpu and profile.gpu_vram_gb:
        # 预留 1GB 给模型参数和系统
        available_mb = (profile.gpu_vram_gb - 1.0) * 1024
    else:
        # CPU 模式：用 1/4 内存
        available_mb = (profile.ram_gb / 4) * 1024

    # 粗算：可用显存 / (单样本 * 模型倍数)
    # 训练时梯度+激活大约是前向的 3-4 倍
    batch_size = int(available_mb / (per_sample_mb * 4))

    # 限制在合理范围
    batch_size = max(16, min(batch_size, 512))

    # 取最近的 2 的幂
    batch_size = 2 ** int(math.log2(batch_size))

    return batch_size


def get_device() -> str:
    """返回最佳可用设备名称"""
    import torch
    if torch.cuda.is_available():
        return "cuda"
    # macOS MPS 支持
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
