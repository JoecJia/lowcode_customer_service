# Skill: 项目同步 (Git Sync)

## 描述
用于将本地的 `customer_service` 项目与远程 Git 仓库进行同步（包括上传本地修改和下载最新文档）。

## 触发条件
- 用户说：“上传我的改动”
- 用户说：“下载最新的文档”
- 用户说：“同步项目”

## 执行方式
该能力目前通过运行脚本 `skills/git_sync/sync_project.ps1` 实现。该脚本已配置远程仓库：`https://github.com/JoecJia/lowcode_customer_service.git`。

## 注意事项
1. **前提条件**：系统必须安装 Git 并配置好 GitHub 访问权限（建议配置 SSH 或使用 Token）。
2. **首次同步**：运行脚本会自动完成初始化和关联。
