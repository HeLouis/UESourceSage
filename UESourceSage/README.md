# UE Source Sage

UE Source Sage 是一个按“学习领域 → Build.cs 子模块”隔离的 Unreal Engine 源码学习框架。目前只包含通用框架，不预置 MassEntity、StateTree 或 Behavior。

## 核心层级

```text
modules/<learning-domain>/
├─ module.yaml                 # 学习领域配置，不授予源码访问权
├─ ROUTER.md
├─ agents/                     # 领域级 Agent
├─ submodules/
│  └─ <build-cs-scope>/
│     ├─ submodule.yaml        # 唯一一个 Build.cs 的严格 allowlist
│     ├─ ROUTER.md
│     ├─ agents/               # 子模块级 Agent
│     ├─ references/
│     ├─ process/
│     ├─ questions/
│     └─ validation/
├─ references/                 # 仅跨子模块知识
├─ process/                    # 学习领域总体阶段
├─ questions/                  # 跨子模块问题
└─ validation/                 # 路由与边界回归场景
```

`validation/` 不是源码审计，也不是普通学习笔记。它保存 Prompt 路由和访问边界的回归测试：例如检查一个问题是否进入正确子模块，以及越界路径是否被拒绝。

## Build.cs 访问边界

每个子模块严格对应一个 Build.cs。该 Build.cs 所在目录自动成为唯一允许源码根；额外的 `.uplugin` 等文件必须单独列入 `allowed_files`。Build.cs 中声明的依赖只记录为边界，不会自动授权读取依赖模块。

如果 Build.cs 路径未知，框架只能先创建学习领域，然后等待用户提供路径或明确授权定位；不能为了自动发现而扫描引擎源码。

源码读取必须经过范围守卫：

```powershell
python skills/ue-source-sage/scripts/sage.py source check <domain-id> <submodule-id> <EngineRelativePath>
python skills/ue-source-sage/scripts/sage.py source read <domain-id> <submodule-id> <EngineRelativePath>
python skills/ue-source-sage/scripts/sage.py source search <domain-id> <submodule-id> <regex>
```

## Agent 三级位置

- 全局：`skills/ue-source-sage/agents/roles/`，只放通用执行角色。
- 学习领域：`modules/<domain>/agents/`，只放领域组织与边界角色。
- 子模块：`modules/<domain>/submodules/<submodule>/agents/`，只放当前 Build.cs 范围的专用分析角色。

更具体的 Agent 可以收紧分析方式，但不能放宽路由、证据、process、questions 或源码 allowlist 规则。默认由当前 Agent 顺序执行；只有用户明确要求且运行环境支持时才并行委派。

## 基础命令

```powershell
python skills/ue-source-sage/scripts/sage.py validate
python skills/ue-source-sage/scripts/sage.py module create ModuleDomain --id module-domain
python skills/ue-source-sage/scripts/sage.py submodule create module-domain Core --id core --build-cs Engine/Plugins/Runtime/Example/Source/Example/Example.Build.cs
python skills/ue-source-sage/scripts/sage.py submodule list module-domain
python skills/ue-source-sage/scripts/sage.py process show module-domain --submodule core
python skills/ue-source-sage/scripts/sage.py question add module-domain --submodule core --text "问题内容" --why "值得缓存的原因"
```

先在 `config/global.yaml` 填写真实的 `engine.source_root` 和目标版本。没有 active submodule 时，框架不允许访问 Unreal 源码。
