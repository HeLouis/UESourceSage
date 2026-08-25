# UE Source Sage Architecture

## 运行模型

UE Source Sage 只有一个主 Agent Runtime。主 Agent 在同一个上下文中，根据当前 process 阶段和用户意图，依次激活适用的角色规范。

```text
Main Learning Agent
├─ global roles
├─ domain roles
└─ submodule roles
```

## 作用域层级

```text
Workspace
├─ config/global.yaml
├─ modules/index.md
├─ .workflow/                 # 临时发现状态
├─ skills/ue-source-sage/     # Skill、角色库、协议、工具、模板
└─ modules/
   └─ <domain>/               # 学习领域
      └─ submodules/<name>/   # 严格一个 Build.cs
```

### 学习领域

学习领域表示一个用户理解上的整体，例如 MassEntity。它维护跨子模块的路由、总体 process、领域级 questions 和 validation，但本身不授予引擎源码访问权。

### 子模块

子模块是源码学习的最小活动范围，严格对应一个 `*.Build.cs`。该 Build.cs 的父目录是唯一递归源码根，额外文件必须显式列入 allowlist。Build.cs 依赖永远只是边界证据。

## 角色规范

```text
skills/ue-source-sage/roles/
modules/<domain>/roles/
modules/<domain>/submodules/<submodule>/roles/
```

有效角色规范由三层叠加：

```text
全局硬规则 + 领域专用规则 + 子模块专用规则
```

更窄作用域只能收紧规则，不能放宽源码、证据、process 或 questions 约束。每次只激活一个有效角色；角色切换由主 Agent 完成。

## 初始化状态

```text
preflight
→ discovery
→ domain confirmation
→ domain creation
→ Build.cs confirmation
→ submodule creation
→ role activation
→ learning process
```

全局配置预检失败时，所有后续工作流阻断。发现阶段在配置的 `engine.source_root`（可用 `--within` 缩小范围）内只做元数据匹配；扫描不需要额外授权，用户确认候选之前不创建领域或子模块。

## 学习产物

- `references/`：渐进式路由和源码证据文档。
- `references/knowledge/`：由 CLI 创建和维护的 canonical 学习文档；`sources.index.md` 是其紧凑目录。
- `process/`：scope、map、model、trace、verify、synthesize 阶段状态。
- `questions/`：可缓存问题及其证据生命周期。
- `validation/`：路由和访问边界回归场景，不是知识库。

阶段退出必须提交工作记录、退出评估、下一阶段交接和证据；`model`/`synthesize` 还必须存在 canonical 文档。作用域 manifest 与全局引擎版本不一致时，学习命令会阻断。

第三阶段加入可执行路由：`route activate/resolve` 固化一个领域、一个子模块、intent、topic、角色和最小索引集合；源码命令必须匹配当前活动路由。版本迁移显式标记旧知识为 `stale_version` 并清除旧路由。
