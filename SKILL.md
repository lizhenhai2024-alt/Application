---
name: patent-figure-annotation-studio
version: 2.1.1
description: 使用本地桌面 UI 完成专利附图中文标注。UI负责打开PDF、编辑序号名称映射、手工确认机械主体和扫描图序号位置；Solver负责Boundary Labeling、全局碰撞求解、画布扩展和Preflight。
language: zh-CN
---

# Patent Figure Annotation Studio V2.1.1

## 使用原则

优先读取原始 PDF。

- 矢量 PDF：通过 PyMuPDF 精确取得原始序号 bbox。
- 扫描 PDF / PNG：不强制 OCR，UI 支持人工点击序号定位。
- 用户拖框定义 Mechanical Body Zone；多子图可定义多个主体。
- Solver 只把新增中文名称放在主体外部。
- 原始机械结构、原序号、原引线和图号不得重绘。

## UI 标准流程

1. 打开 PDF / 图片。
2. 填写完整专利文件名。
3. 导入/粘贴序号名称。
4. 每个子图拖框主体：
   - rect：剖面图/纵向结构；
   - circle：圆形阀片/环形件。
5. 扫描图中缺坐标的序号，使用手动点击定位。
6. 处理当前页。
7. 只有 Preflight PASS 才保存。
