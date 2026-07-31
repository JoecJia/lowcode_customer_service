#!/usr/bin/env bash
# Intelligent Customer Service - Quick Start (Linux)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Intelligent Customer Service Starting..."
echo "========================================"

# 检查 Python 环境
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found. Please install Python 3.10+."
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

# 检查 .env 是否存在
if [ ! -f ".env" ]; then
    echo "[WARN] .env not found. Creating default .env..."
    cat > .env << 'EOF'
ARK_API_KEY=your-ark-api-key
JWT_SECRET=change-me-in-production
HF_ENDPOINT=https://hf-mirror.com
EOF
    echo "[OK] .env created."
fi

# 启动后端
echo ""
echo "[1/2] Starting Backend (http://localhost:8000)..."
$PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
sleep 2
echo "  Backend started (PID: $BACKEND_PID)"

# 启动前端
echo ""
echo "[2/2] Starting Frontend (http://localhost:5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
sleep 3

echo ""
echo "========================================"
echo "  All services started!"
echo "========================================"
echo ""
echo "  Customer Chat : http://localhost:5173/"
echo "  Admin Panel   : http://localhost:5173/admin"
echo "  Backend API   : http://localhost:8000"
echo ""
echo "  Backend PID  : $BACKEND_PID"
echo "  Frontend PID : $FRONTEND_PID"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "========================================"

# 捕获 Ctrl+C 后清理子进程
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

wait
