# CHANGELOG

## 2.0.0
- 从 Prompt-driven 布局升级为 Solver-driven 布局。
- 引入 Boundary Labeling 架构。
- 引入 Mechanical Body Zone，禁止文字进入主体内部白色空腔。
- 引入 rect / circle 两种主体模型。
- 引入同侧 Lane 与顺序约束。
- 引入 reference token 白名单。
- 引入全局 MILP 求解；预留 OR-Tools CP-SAT 后端。
- 引入画布自动扩展。
- 引入最终 Preflight report。
- 明确扫描图默认不使用 OCR。
