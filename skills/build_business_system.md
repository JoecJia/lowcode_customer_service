# Skill: 搭建业务系统 (Build Business System)

## 描述
用于引导用户在低代码平台上快速搭建符合业务需求的系统（如：学工管理系统、实习系统、招生系统等）。该技能会根据用户描述的场景，推荐合适的表单模板、流程逻辑和角色配置。

## 输入参数
- `system_name` (string): 欲搭建的系统名称（如“实验室管理系统”）。
- `business_scenarios` (string): 具体的业务场景描述。
- `core_requirements` (list): 核心功能需求（如：审批流、数据报表、AI填表）。

## 输出
- `template_recommendation`: 推荐的表单模板列表。
- `workflow_logic`: 核心审批或业务流转建议。
- `role_config`: 建议的角色权限划分（管理员、编辑者、查看者）。

## 使用场景
当用户表达“我想建一个系统”、“帮我设计一个学工系统”或“怎么搭建实验室管理系统？”时调用。
