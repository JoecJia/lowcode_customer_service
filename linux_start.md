# Linux 系统启动指南

## 环境要求

| 依赖 | 最低版本 |
|------|----------|
| Python | 3.10+ |
| Node.js | 20+ |
| npm | 随 Node.js |

## 1. 克隆项目并进入目录

```bash
git clone http://10.0.9.250/product-doc/smart-customer-service.git
cd smart-customer-service
```

## 2. 配置环境变量

创建 `.env` 文件（必须包含 ARK_API_KEY）：

```bash
cat > .env << 'EOF'
ARK_API_KEY=your-ark-api-key
JWT_SECRET=change-me-in-production
HF_ENDPOINT=https://hf-mirror.com
EOF
```

> 生产环境请修改 `JWT_SECRET` 为随机字符串。

## 3. 安装依赖

```bash
# Python 后端依赖
cd backend
pip install -r requirements.txt
cd ..

# 前端依赖
cd frontend
npm install
cd ..
```

## 4. 启动项目

### 方式一：一键启动（推荐）

```bash
chmod +x linux_start.sh
./linux_start.sh
```

### 方式二：分别启动

**终端 1 - 启动后端：**

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**终端 2 - 启动前端：**

```bash
cd frontend && npm run dev
```

### 方式三：生产模式（前端构建后由后端托管）

```bash
# 构建前端
cd frontend && npm run build && cd ..

# 启动后端（自动托管前端静态文件）
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## 启动后访问

| 页面 | 地址 |
|------|------|
| 客户对话 | http://localhost:5173/ |
| 登录页 | http://localhost:5173/login |
| 管理后台 | http://localhost:5173/admin |
| 后端 API | http://localhost:8000 |
| 健康检查 | http://localhost:8000/health |

## 常见问题

### 首次启动下载模型慢

首次启动时 `sentence-transformers` 会自动下载 BGE 中文向量模型（约 400MB）。已配置 `HF_ENDPOINT=https://hf-mirror.com` 国内镜像加速。

### 知识库搜索无结果

需要先在管理后台执行"上下文转化"生成 FAISS 索引，或手动构建：

```bash
cd agent_config/context
python build_faiss_index.py
```

### 端口被占用

```bash
# 修改后端端口
PORT=8080 uvicorn backend.main:app --host 0.0.0.0 --port 8080

# 修改前端端口（vite.config.ts 中 proxy target 也要同步修改）
cd frontend && npm run dev -- --port 3000
```

### 后台运行

```bash
# 后端后台运行
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

# 前端后台运行
cd frontend && nohup npm run dev > frontend.log 2>&1 &
```

---

## Jenkins CI/CD 自动部署

### 整体流程

```
Git Push → Jenkins 拉取代码 → 安装依赖 → 构建前端 → 打包 → SCP 上传服务器 → 重启服务
```

### 前置准备

**Jenkins 服务器需安装：**
- Git 插件
- Node.js 20+ 和 npm
- Python 3.10+ 和 pip
- SSH 插件 / Credentials 插件

**部署目标服务器需准备：**

```bash
# 1. 创建部署目录
sudo mkdir -p /opt/smart-customer-service
sudo chown $USER:$USER /opt/smart-customer-service

# 2. 安装 Python 依赖（首次）
cd /opt/smart-customer-service
pip install -r backend/requirements.txt

# 3. 配置 systemd 服务（见下方）
```

**目标服务器 systemd 服务文件** `/etc/systemd/system/customer-service.service`：

```ini
[Unit]
Description=Smart Customer Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/smart-customer-service
EnvironmentFile=/opt/smart-customer-service/.env
ExecStart=/usr/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable customer-service
```

### Jenkinsfile（Pipeline 脚本）

在项目根目录创建 `Jenkinsfile`：

```groovy
pipeline {
    agent any

    environment {
        // 部署目标服务器配置
        DEPLOY_HOST     = '10.0.9.250'
        DEPLOY_USER     = 'deploy'
        DEPLOY_PATH     = '/opt/smart-customer-service'
        DEPLOY_PORT     = '22'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                echo "Branch: ${env.BRANCH_NAME}, Commit: ${env.GIT_COMMIT.take(8)}"
            }
        }

        stage('Setup Python') {
            steps {
                sh '''
                    cd backend
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Build Frontend') {
            steps {
                sh '''
                    cd frontend
                    npm install
                    npm run build
                '''
            }
        }

        stage('Package') {
            steps {
                sh '''
                    # 打包需要部署的文件
                    tar -czf release.tar.gz \
                        backend/ \
                        frontend/dist/ \
                        agent_config/ \
                        linux_start.sh \
                        requirements.txt \
                        --exclude='backend/data' \
                        --exclude='backend/__pycache__' \
                        --exclude='backend/.venv' \
                        --exclude='node_modules' \
                        --exclude='.git'
                '''
            }
        }

        stage('Deploy') {
            steps {
                // 上传部署包到目标服务器
                sshagent(['deploy-server-key']) {
                    sh '''
                        scp -P ${DEPLOY_PORT} -o StrictHostKeyChecking=no \
                            release.tar.gz \
                            ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/

                        ssh -p ${DEPLOY_PORT} -o StrictHostKeyChecking=no \
                            ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "cd ${DEPLOY_PATH} && tar -xzf release.tar.gz && rm release.tar.gz"
                    '''
                }
            }
        }

        stage('Restart Service') {
            steps {
                sshagent(['deploy-server-key']) {
                    sh '''
                        ssh -p ${DEPLOY_PORT} -o StrictHostKeyChecking=no \
                            ${DEPLOY_USER}@${DEPLOY_HOST} \
                            "sudo systemctl restart customer-service && sudo systemctl status customer-service --no-pager"
                    '''
                }
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    sleep 5
                    curl -f http://${DEPLOY_HOST}:8000/health || exit 1
                '''
            }
        }
    }

    post {
        success {
            echo 'Deploy succeeded!'
            echo "Service available at: http://${DEPLOY_HOST}:8000"
        }
        failure {
            echo 'Deploy failed! Please check the logs.'
        }
        always {
            cleanWs()
        }
    }
}
```

### Jenkins 配置步骤

1. **添加 SSH 凭据** — Jenkins 管理 → Credentials → 添加 SSH Private Key（用于连接部署服务器）

2. **（可选）设置 Webhook** — 在 GitLab 项目设置中配置 Webhook 指向 `http://<jenkins-host>:8080/gitlab-webhook/`，实现 Push 自动触发构建

3. **创建 Pipeline 任务** — Jenkins 新建任务 → Pipeline → Pipeline script from SCM → 填入 Git 仓库地址

### 目标服务器快速部署脚本

首次在服务器上一键初始化环境：

```bash
#!/usr/bin/env bash
# 在目标服务器上执行：首次环境初始化
set -e

DEPLOY_PATH="/opt/smart-customer-service"
PYTHON="/usr/bin/python3"

# 创建目录
sudo mkdir -p $DEPLOY_PATH
sudo chown -R $USER:$USER $DEPLOY_PATH

# 安装系统依赖
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm curl

# 安装 Python 依赖
cd $DEPLOY_PATH/backend
pip3 install -r requirements.txt
cd $DEPLOY_PATH

# 安装 Node 依赖并构建前端
cd $DEPLOY_PATH/frontend
npm install
npm run build
cd $DEPLOY_PATH

# 创建 .env（替换为真实 Key）
cat > .env << 'EOF'
ARK_API_KEY=your-ark-api-key
JWT_SECRET=$(openssl rand -hex 32)
HF_ENDPOINT=https://hf-mirror.com
EOF

# 配置 systemd
sudo tee /etc/systemd/system/customer-service.service << SYSTEMD
[Unit]
Description=Smart Customer Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_PATH
EnvironmentFile=$DEPLOY_PATH/.env
ExecStart=$PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD

sudo systemctl daemon-reload
sudo systemctl enable customer-service
sudo systemctl start customer-service

echo "Deploy done! Check: curl http://localhost:8000/health"
```
