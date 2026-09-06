# Patent Figure Annotation Studio V2.1.1

本地桌面程序，用于专利附图的**中文零件名称标注、页面净化、完整专利文件名归档和保真清晰度增强**。

核心架构：**原始 PDF / 图片 + Boundary Labeling + Mechanical Body Zone + 全局约束求解 + Preflight**。

## 主要特点

- 优先读取原始 PDF；
- 矢量 PDF 使用 PyMuPDF 读取原始序号 bbox；
- 扫描 PDF / PNG 不强制 OCR，可在 UI 中手动点击序号定位；
- 中文名称仅放在 Mechanical Body Zone 外部；
- 密集序号采用 LEFT / RIGHT / TOP / BOTTOM 外侧 Lane；
- 完整文字 bbox 碰撞检测；
- 原始机械结构、原始序号、原始引线和图号不重绘；
- 空间不足时扩展白色画布；
- 只有 Preflight PASS 才输出。

## UI 工作流

1. 打开原始 PDF / 图片；
2. 导入或粘贴 `序号 → 中文名称`；
3. 对每个子图定义机械主体：
   - 剖面图/纵向结构：矩形主体；
   - 圆环/阀片俯视图：圆形主体；
4. 扫描图中缺少坐标的序号，用“添加序号并在图上点击”定位；
5. 点击“处理当前页”；
6. Solver 自动进行外侧分栏、顺序约束、碰撞检测和画布扩展；
7. Preflight PASS 后保存高分辨率 PNG。

## Windows 启动

推荐 Python 3.11 或 3.12。

最方便的方式：

```bat
start_windows.bat
```

启动脚本会：

1. 自动寻找 Python 3.10–3.13；
2. 检查 Tkinter；
3. 自动创建 `.venv`；
4. 首次运行安装依赖；
5. 将错误写入 `startup.log`。

如果启动失败：

```bat
diagnose_windows.bat
```

会生成 `diagnose.txt`。也可以使用：

```bat
reset_environment.bat
```

删除本程序的 `.venv`，下次启动重新创建环境。

## 手动安装

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

## 依赖

- Pillow
- NumPy
- SciPy
- PyMuPDF
- Tkinter（python.org 官方 Windows Python 通常自带）

## 标注样式

- 新增中文内容统一深蓝色：`#123A63`；
- 完整专利文件名仅作为顶部归档信息，不作为大标题；
- 默认不新增技术引线；
- 中文标签以原始序号为锚点，同时以“不覆盖机械结构”为硬约束。

## 文件说明

- `app.py`：桌面 UI；
- `layout_solver.py`：Boundary Labeling / MILP 布局求解器；
- `start_windows.bat`：Windows 一键启动；
- `diagnose_windows.bat`：启动环境诊断；
- `reset_environment.bat`：重建虚拟环境；
- `mapping_example.txt`：序号名称示例；
- `SKILL.md`：Skill 调用规范；
- `SOLVER_CHANGELOG.md`：Solver 版本说明。
