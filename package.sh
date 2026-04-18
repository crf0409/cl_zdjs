#!/bin/bash
# ============================================================
# 智能交通流量预测系统（交通数据可视化）- 项目打包脚本
# 用法: bash package.sh
# 输出: smart_traffic_system.zip
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_NAME="smart_traffic_system"
OUTPUT_ZIP="${PROJECT_DIR}/${OUTPUT_NAME}.zip"

echo "============================================"
echo "  智能交通流量预测系统 - 打包脚本"
echo "============================================"
echo ""

# 删除旧的打包文件
rm -f "$OUTPUT_ZIP"

cd "$PROJECT_DIR"

echo "[1/4] 收集后端文件..."
echo "[2/4] 收集CenterPoint感知模块..."
echo "[3/4] 收集交通数据集..."
echo "[4/4] 收集数据库和文档..."

# 打包 (排除不需要的文件)
zip -r "$OUTPUT_ZIP" \
    README.md \
    .env.example \
    database/ \
    project3_traffic_prediction/ \
    project2_centerpoint/CenterPoint/det3d/ \
    project2_centerpoint/CenterPoint/tools/ \
    project2_centerpoint/CenterPoint/configs/ \
    project2_centerpoint/CenterPoint/docs/ \
    project2_centerpoint/CenterPoint/README.md \
    project2_centerpoint/CenterPoint/requirements.txt \
    project2_centerpoint/CenterPoint/setup.sh \
    project2_centerpoint/CenterPoint/LICENSE \
    project2_centerpoint/nuscenes_data/ \
    project2_centerpoint/nuScenes_mini/ \
    project2_centerpoint/generated_assets/ \
    -x "*.pyc" \
    -x "*__pycache__*" \
    -x "*.egg-info*" \
    -x "*/.git/*" \
    -x "*/node_modules/*" \
    -x "*.pt" \
    -x "*.pth" \
    -x "*.so" \
    -x "*/.config/*" \
    -x "*/venv/*" \
    -x "*/.venv/*" \
    -x "*/staticfiles/*" \
    > /dev/null 2>&1

# 显示结果
SIZE=$(du -sh "$OUTPUT_ZIP" | cut -f1)
echo ""
echo "============================================"
echo "  打包完成!"
echo "  文件: $OUTPUT_ZIP"
echo "  大小: $SIZE"
echo "============================================"
echo ""
echo "包含内容:"
echo "  - 后端源码 (Django + ML模型)"
echo "  - 前端模板 (26个HTML页面)"
echo "  - CenterPoint 3D感知模块"
echo "  - nuScenes迷你验证集 (交通数据集)"
echo "  - 数据库SQL脚本 + 设计文档"
echo "  - 完整部署说明文档"
