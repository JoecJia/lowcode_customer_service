# Skill: 项目同步 (Git Sync)

## 描述
用于将本地的 `customer_service` 项目与远程 Git 仓库进行同步（包括上传本地修改和下载最新文档）。

## 触发条件
- 用户说：“上传我的改动”
- 用户说：“下载最新的文档”
- 用户说：“同步项目”

## 执行方式
该能力通过运行项目内的同步脚本实现，支持 Windows / macOS：
- Windows（PowerShell）：`skills/git_sync/sync_project.ps1`
- macOS（bash/zsh）：`skills/git_sync/sync_project.sh`

## 注意事项
1. **前提条件**：系统必须安装 Git 并配置好 GitHub 访问权限（建议配置 SSH 或使用 Token）。
2. **远程地址**：脚本默认使用 SSH 远程 `git@github.com:JoecJia/lowcode_customer_service.git`，更适合跨平台与稳定同步。
3. **执行参数**：
   - `Mode`：
     - `pull`：仅下载远端最新内容（`git pull --rebase`）
     - `push`：提交本地改动并推送（会先 `pull --rebase` 再推送）
     - `sync`：默认，与 `push` 行为一致
   - `CommitMessage`（仅 `push/sync`）：提交信息
   - `RemoteUrl`（可选）：远程仓库地址，默认 SSH
4. **首次同步**：若遇到 `Permission denied (publickey)`，需要先在 GitHub 添加本机 SSH 公钥，并通过 `ssh -T git@github.com` 验证。

## 运行示例
- Windows（PowerShell）：
  - 下载最新文档：`pwsh -File skills/git_sync/sync_project.ps1 -Mode pull`
  - 上传改动：`pwsh -File skills/git_sync/sync_project.ps1 -Mode sync -CommitMessage "docs: update"`
- macOS（bash/zsh）：
  - 下载最新文档：`bash skills/git_sync/sync_project.sh pull`
  - 上传改动：`bash skills/git_sync/sync_project.sh sync "docs: update"`
