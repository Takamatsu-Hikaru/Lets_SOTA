"""
数据集注册中心
管理所有可用的数据集和对应的 DataLoader 工厂
"""

import os
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from .models import db, Dataset as DatasetModel


# 数据集根目录
DATASET_ROOT = os.environ.get("DATASET_ROOT", os.path.join(os.getcwd(), "datasets"))


# ============================================================
#  数据集注册表
# ============================================================

DATASET_REGISTRY = {
    "mnist": {
        "name": "MNIST",
        "description": "28x28 手写数字，10 分类，经典入门数据集",
        "input_shape": "1,28,28",
        "num_classes": 10,
        "train_size": 60000,
        "test_size": 10000,
        "loader_fn": "_load_mnist",
    },
    "fashion-mnist": {
        "name": "Fashion-MNIST",
        "description": "28x28 时尚单品，10 分类，MNIST 难度升级版",
        "input_shape": "1,28,28",
        "num_classes": 10,
        "train_size": 60000,
        "test_size": 10000,
        "loader_fn": "_load_fashion_mnist",
    },
    "cifar10": {
        "name": "CIFAR-10",
        "description": "32x32 彩色图片，10 分类，经典 CV benchmark",
        "input_shape": "3,32,32",
        "num_classes": 10,
        "train_size": 50000,
        "test_size": 10000,
        "loader_fn": "_load_cifar10",
    },
    "cifar100": {
        "name": "CIFAR-100",
        "description": "32x32 彩色图片，100 分类，精细分类挑战",
        "input_shape": "3,32,32",
        "num_classes": 100,
        "train_size": 50000,
        "test_size": 10000,
        "loader_fn": "_load_cifar100",
    },
    "svhn": {
        "name": "SVHN",
        "description": "32x32 街景门牌号数字，10 分类，真实世界 OCR 挑战",
        "input_shape": "3,32,32",
        "num_classes": 10,
        "train_size": 73257,
        "test_size": 26032,
        "loader_fn": "_load_svhn",
    },
    "imagenet-tiny": {
        "name": "Tiny ImageNet",
        "description": "64x64 彩色图片，200 分类，ImageNet 缩小版",
        "input_shape": "3,64,64",
        "num_classes": 200,
        "train_size": 100000,
        "test_size": 10000,
        "loader_fn": "_load_tiny_imagenet",
    },
}


def seed_datasets():
    """初始化数据集表"""
    for ds_id, info in DATASET_REGISTRY.items():
        if not DatasetModel.query.get(ds_id):
            db.session.add(DatasetModel(
                id=ds_id,
                name=info["name"],
                description=info["description"],
                input_shape=info["input_shape"],
                num_classes=info["num_classes"],
                train_size=info["train_size"],
                test_size=info["test_size"],
            ))
    db.session.commit()


def get_dataloaders(dataset_id: str, batch_size: int = 64, num_workers: int = 2):
    """
    返回 (train_loader, test_loader)
    """
    info = DATASET_REGISTRY.get(dataset_id)
    if not info:
        raise ValueError(f"Unknown dataset: {dataset_id}")

    loader_fn = globals()[info["loader_fn"]]
    return loader_fn(batch_size, num_workers)


# ============================================================
#  DataLoader 工厂函数
# ============================================================

def _load_mnist(batch_size, num_workers):
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    train = datasets.MNIST(DATASET_ROOT, train=True, download=True, transform=transform)
    test = datasets.MNIST(DATASET_ROOT, train=False, transform=transform)
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        DataLoader(test, batch_size=batch_size, shuffle=False, num_workers=num_workers),
    )


def _load_fashion_mnist(batch_size, num_workers):
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.2860,), (0.3530,)),
    ])
    train = datasets.FashionMNIST(DATASET_ROOT, train=True, download=True, transform=transform)
    test = datasets.FashionMNIST(DATASET_ROOT, train=False, transform=transform)
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        DataLoader(test, batch_size=batch_size, shuffle=False, num_workers=num_workers),
    )


def _load_cifar10(batch_size, num_workers):
    train_transform = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])
    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
    ])
    train = datasets.CIFAR10(DATASET_ROOT, train=True, download=True, transform=train_transform)
    test = datasets.CIFAR10(DATASET_ROOT, train=False, transform=test_transform)
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        DataLoader(test, batch_size=batch_size, shuffle=False, num_workers=num_workers),
    )


def _load_cifar100(batch_size, num_workers):
    train_transform = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761)),
    ])
    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761)),
    ])
    train = datasets.CIFAR100(DATASET_ROOT, train=True, download=True, transform=train_transform)
    test = datasets.CIFAR100(DATASET_ROOT, train=False, transform=test_transform)
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        DataLoader(test, batch_size=batch_size, shuffle=False, num_workers=num_workers),
    )


    train_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4377, 0.4438, 0.4728), (0.1980, 0.2010, 0.1970)),
    ])
    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4377, 0.4438, 0.4728), (0.1980, 0.2010, 0.1970)),
    ])
    train = datasets.SVHN(DATASET_ROOT, split='train', download=True, transform=train_transform)
    test = datasets.SVHN(DATASET_ROOT, split='test', download=True, transform=test_transform)
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        DataLoader(test, batch_size=batch_size, shuffle=False, num_workers=num_workers),
    )


def _load_tiny_imagenet(batch_size, num_workers):
    """Tiny ImageNet (200 classes, 64x64)"""
    train_transform = transforms.Compose([
        transforms.RandomCrop(64, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.4802, 0.4481, 0.3975), (0.2302, 0.2265, 0.2262)),
    ])
    test_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4802, 0.4481, 0.3975), (0.2302, 0.2265, 0.2262)),
    ])
    train = datasets.ImageFolder(
        os.path.join(DATASET_ROOT, 'tiny-imagenet-200', 'train'),
        transform=train_transform
    )
    test = datasets.ImageFolder(
        os.path.join(DATASET_ROOT, 'tiny-imagenet-200', 'val'),
        transform=test_transform
    )
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=num_workers),
        DataLoader(test, batch_size=batch_size, shuffle=False, num_workers=num_workers),
    )
