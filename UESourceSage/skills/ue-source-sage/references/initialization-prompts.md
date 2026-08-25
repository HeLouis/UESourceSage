# Domain Initialization Prompts

These are interaction contracts, not domain knowledge. Keep them concise and ask only the next blocking question.

## Domain Intake

```text
我已识别到学习领域：{domain_name}。
当前目标引擎版本：{engine_version}。

请选择下一步：
1. 只创建学习领域空框架；
2. 提供一个明确的 Build.cs 路径并开始该子模块；
3. 先做只读的 Build.cs 候选发现，再由你确认候选。
```

## Missing Engine Root

```text
当前全局配置未通过预检：没有有效的 engine.source_root。
请先配置绝对的 Unreal Engine 源码根目录。配置通过前，不会创建学习领域、发现 Build.cs 或读取源码。
```

## Metadata-only Discovery

```text
“{query}”存在多个可能的 Unreal 模块。
我会在以下相对目录内只搜索路径名、*.Build.cs 和 *.uplugin 文件名：
{discovery_root}

不会读取 .h/.cpp 实现，也不会自动创建领域或子模块。
下面是扫描得到的候选，请确认要学习的领域和具体 Build.cs。
```

## Candidate Confirmation

```text
发现候选学习领域/Build.cs：
{candidate_table}

每个确认的 Build.cs 会生成一个独立子模块，不会合并多个 Build.cs。
请选择要纳入的候选，或只确认学习领域、稍后再创建子模块。
```

## Completion Summary

```text
学习领域 {domain_name} 已初始化。

已确认子模块：
{submodule_table}

领域 process 当前状态：{domain_process_state}
下一步请选择要激活的一个子模块：{next_action}
```
