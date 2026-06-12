FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载数据集（构建时下载，运行时直接用）
RUN python -c "
from torchvision import datasets
datasets.MNIST('/app/datasets', download=True)
datasets.CIFAR10('/app/datasets', download=True)
datasets.FashionMNIST('/app/datasets', download=True)
"

# 应用代码
COPY . .

# 暴露端口
EXPOSE 5000

# 启动
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]
