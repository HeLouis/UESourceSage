# UE Source Sage

UE Source Sage 是一个由一个主 Agent 执行的 Unreal Engine 源码学习工作流。它用学习领域、Build.cs 子模块和角色规范隔离上下文。

## 总体架构

```text
全局配置 + preflight
        ↓
唯一主 Agent Runtime
        ↓
角色规范（全局 / 学习领域 / 子模块）
        ↓
学习领域 Module
        ↓
单 Build.cs 子模块 Submodule
        ↓
路由 / Process / Questions / References / Validation
```

### 唯一主 Agent

整个工作流只有一个运行主体。它根据当前阶段和任务意图激活不同角色规范，例如：

```text
source-mapper → callflow-tracer → boundary-guard → question-curator
```

这是同一个主 Agent 在不同阶段切换角色规范。

### 角色规范层

```text
skills/ue-source-sage/roles/                         # 全局角色
modules/<domain>/roles/                              # 学习领域角色
modules/<domain>/submodules/<submodule>/roles/       # 子模块角色
```

领域和子模块可以定义专用角色，约束该领域的术语、学习重点、输出格式和阶段任务；它们只能收紧全局规则，不能扩大源码访问范围。

`skills/ue-source-sage/skill-ui.yaml` 是 Skill 平台的 UI 元数据，不是运行时角色。

## 学习领域与子模块

```text
modules/<learning-domain>/
├─ module.yaml                 # 学习领域配置，不授予源码访问权
├─ ROUTER.md
├─ roles/                      # 领域角色规范
├─ submodules/
│  └─ <build-cs-scope>/
│     ├─ submodule.yaml        # 唯一一个 Build.cs 的严格 allowlist
│     ├─ ROUTER.md
│     ├─ roles/                # 子模块角色规范
│     ├─ references/
│     ├─ process/
│     ├─ questions/
│     └─ validation/
├─ references/                 # 仅跨子模块知识
├─ process/                    # 学习领域总体阶段
├─ questions/                  # 跨子模块问题
└─ validation/                 # 路由与边界回归场景
```

一个子模块严格对应一个 `*.Build.cs`。Build.cs 依赖只记录为边界，不会自动授权读取依赖模块。

canonical 学习文档位于每个领域或子模块的 `references/knowledge/`，由 `sources.index.md` 自动维护；问题可以从子模块显式提升到领域，并关联到这些文档。

canonical 文档必须包含非空 Quick Answer 和 Source Trail。可使用 `knowledge update/validate/archive` 维护生命周期；归档会同步修复问题中的文档链接。

## 初始化与源码边界

```text
preflight
→ metadata-only Build.cs 发现
→ 用户确认候选学习领域
→ 创建领域
→ 用户确认 Build.cs
→ 创建一对一子模块
→ 激活一个领域/子模块 route
→ 主 Agent 激活第一个角色并开始学习
```

发现阶段只读取路径名、`*.Build.cs` 和 `*.uplugin` 文件名，不读取实现源码；这是只读候选扫描，不需要额外授权。没有 active submodule 和 active route 时，框架不允许访问 Unreal 源码。

## 基础命令

```powershell
python skills/ue-source-sage/scripts/sage.py preflight
python skills/ue-source-sage/scripts/sage.py validate
python skills/ue-source-sage/scripts/sage.py discover build-cs <query> --within <EngineRelativeRoot>
python skills/ue-source-sage/scripts/sage.py module create <DomainName> --id <domain-id> --from-discovery
python skills/ue-source-sage/scripts/sage.py module confirm <domain-id> --build-cs <EngineRelativeBuildCs>
python skills/ue-source-sage/scripts/sage.py process show <domain-id> --submodule <submodule-id>
python skills/ue-source-sage/scripts/sage.py question list <domain-id> --submodule <submodule-id>
python skills/ue-source-sage/scripts/sage.py knowledge create <domain-id> --submodule <submodule-id> --title "<Document title>" --answer "<Quick answer>" --source "<EngineRelativeSourcePath>:<line>"
python skills/ue-source-sage/scripts/sage.py question promote <domain-id> Q-0001 --from-submodule <submodule-id> --reason "<why this spans submodules>"
python skills/ue-source-sage/scripts/sage.py route activate <domain-id> <submodule-id> --intent explain --topic "<topic>"
python skills/ue-source-sage/scripts/sage.py version status <domain-id>
python skills/ue-source-sage/scripts/sage.py version migrate <domain-id> --reason "<engine upgrade reason>"
```

以上命令只是通用流程示例，不代表仓库已经创建了某个具体学习领域或子模块。实际学习时，先由 metadata-only discovery 输出候选，再由用户确认领域和具体 Build.cs；每确认一个 Build.cs，才创建对应的一对一子模块。

先在 `config/global.yaml` 配置真实的 `engine.source_root` 和目标版本。
