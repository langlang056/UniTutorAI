#!/bin/bash
# PPT Helper 手动安装 Python 3.11 (适用于 Ubuntu/Debian)

set -e

echo "========================================"
echo "  安装 Python 3.11"
echo "========================================"

# 检查是否为 root
if [[ $EUID -ne 0 ]]; then
   echo "请使用 sudo 运行此脚本"
   exit 1
fi

# 检测系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
else
    echo "无法检测操作系统"
    exit 1
fi

echo "检测到系统: $OS $VER"

# Ubuntu/Debian 系统
if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
    echo "添加 deadsnakes PPA..."
    apt update
    apt install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update
    
    echo "安装 Python 3.11..."
    apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
    
    echo "验证安装..."
    python3.11 --version
    
    echo "✓ Python 3.11 安装成功!"

# CentOS/RHEL 系统
elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]]; then
    echo "安装开发工具..."
    yum groupinstall -y "Development Tools"
    yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel wget
    
    echo "下载 Python 3.11 源码..."
    cd /tmp
    wget https://www.python.org/ftp/python/3.11.6/Python-3.11.6.tgz
    tar xzf Python-3.11.6.tgz
    cd Python-3.11.6
    
    echo "编译安装 Python 3.11..."
    ./configure --enable-optimizations
    make altinstall
    
    echo "验证安装..."
    python3.11 --version
    
    echo "✓ Python 3.11 安装成功!"
    
else
    echo "不支持的操作系统: $OS"
    echo "请手动安装 Python 3.11 或使用系统默认 Python 3"
    exit 1
fi

echo ""
echo "现在可以运行部署脚本:"
echo "  sudo ./deploy.sh"
