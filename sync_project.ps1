# 极简同步脚本 (Simplified Sync Script)
param (
    [string]$CommitMessage = "Update"
)

Write-Host ">>> 正在检查 Git 状态..." -ForegroundColor Cyan

# 1. 如果没有 .git 文件夹则初始化
if (-not (Test-Path ".git")) {
    Write-Host "初始化本地仓库..."
    git init
}

# 2. 尝试关联远程仓库 (如果失败说明已关联，忽略报错)
Write-Host "正在确认远程仓库..."
git remote add origin https://github.com/JoecJia/lowcode_customer_service.git 2>$null

# 3. 拉取远程更新
Write-Host "正在同步远程文档..."
git pull origin main --rebase

# 4. 提交本地修改
Write-Host "正在保存本地修改..."
git add .
git commit -m "$CommitMessage"

# 5. 推送到远程
Write-Host "正在上传到 GitHub..."
git branch -M main
git push -u origin main

Write-Host ">>> 同步完成！" -ForegroundColor Green
