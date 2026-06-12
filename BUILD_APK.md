# 618 比价监测 - APK 打包指南

## 准备工作

将 `F:\codex\测试\kivy_app` 整个文件夹压缩为 `kivy_app.zip`

## Google Colab 打包步骤

打开 https://colab.research.google.com/ ，依次运行以下单元格：

### 单元格 1：安装依赖（约2分钟）
```python
!pip install buildozer cython
!sudo apt update
!sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
```

### 单元格 2：上传并解压项目
```python
from google.colab import files
uploaded = files.upload()  # 选择 kivy_app.zip

!unzip kivy_app.zip -d /content/
%cd /content/kivy_app
!ls -la
```

### 单元格 3：构建 APK（约20-40分钟）
```python
!buildozer -v android debug
```

### 单元格 4：下载 APK
```python
from google.colab import files
files.download('/content/kivy_app/bin/dealmonitor-1.0-arm64-v8a-debug.apk')
```

## 安装到手机

1. 将 APK 传到 Redmi K80 Pro
2. 设置 → 安全 → 允许安装未知来源应用
3. 安装后打开，授予通知和后台权限

## HyperOS 特别设置
- 长按应用 → 应用信息 → 通知管理 → 开启悬浮通知
- 应用信息 → 省电策略 → 无限制
- 应用信息 → 自启动 → 开启