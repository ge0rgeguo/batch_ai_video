# 🎬 AI 视频批量生成平台（Sora 2）

基于 Sora 2 的批量视频生成 Web 应用，支持生产服务器部署和 Google Colab 测试。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)

---

## ✨ 主要功能

### 📹 视频生成
- ✅ **Sora 2 模型**支持
- ✅ 支持图片+文本生成视频
- ✅ 自定义参数: 方向、尺寸、时长
- ✅ 批量生成(1-50 个视频)
- ✅ 任务队列管理
- ✅ 积分系统（10秒15分，5秒8分）

### 👤 用户管理
- ✅ 用户认证与会话管理
- ✅ 密码加密存储 (bcrypt)
- ✅ 用户数据隔离
- ✅ 支持多用户并发
- ✅ 管理员积分调整

### 📊 任务管理
- ✅ 批次管理
- ✅ 实时任务进度查看
- ✅ 任务重试机制
- ✅ 结果下载与 ZIP 打包（支持远程视频URL）

### 🎨 用户界面
- ✅ 现代化响应式设计
- ✅ 四列布局(图片、Prompt、参数、批次列表)
- ✅ 实时状态更新
- ✅ Toast 消息提示

---

## 🚀 快速开始

### 🌐 生产服务器部署（推荐）

**适用场景**: 24/7 稳定运行，使用自定义域名

**一键部署脚本**:

```bash
# 下载并执行部署脚本
curl -fsSL https://raw.githubusercontent.com/ge0rgeguo/batch_ai_video/main/deploy/setup_zuoshipin_server.sh -o setup.sh
sudo bash setup.sh
```

**部署脚本功能**:
- ✅ 自动安装系统依赖（git, nginx, python, ufw, fail2ban）
- ✅ 创建应用用户与目录结构
- ✅ 克隆代码仓库并安装 Python 依赖
- ✅ 配置环境变量（提示输入 YUNWU_API_KEY）
- ✅ 初始化数据库
- ✅ 配置 systemd 服务（单实例）
- ✅ 配置 Nginx 反向代理（支持 Cloudflare Origin 证书）

**部署后**:
- 服务地址: `https://zuoshipin.net`（需配置 Cloudflare DNS）
- 服务管理: `sudo systemctl restart ai-batch`
- 查看日志: `sudo journalctl -u ai-batch -f`

**详细说明**: 脚本会自动检测 Cloudflare Origin 证书，有则启用 HTTPS，否则先运行 HTTP。

### 🧪 Google Colab 测试

**适用场景**: 快速测试、演示、开发验证

**可选方式**:

1. **ngrok 方式**（推荐新手）:
   - 打开 `colab_webapp_ngrok.ipynb`
   - 按 Cell 顺序执行
   - 获取临时公网URL

2. **Cloudflare Tunnel 方式**（推荐自定义域名）:
   - 打开 `colab_webapp_cloudflare.ipynb`
   - 配置 Cloudflare Tunnel
   - 使用自定义域名访问

**注意**: Colab 会话结束后数据会丢失，仅用于测试。

### 💻 本地开发运行

```bash
# 1. 克隆项目
git clone https://github.com/ge0rgeguo/batch_ai_video.git
cd batch_ai_video

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # 或 Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 设置环境变量
export YUNWU_API_KEY="sk-your-api-key"
export PUBLIC_BASE_URL="http://localhost:8000"

# 5. 初始化数据库
python -c "from server.db import init_db; init_db()"

# 6. 运行应用
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

访问: http://localhost:8000

---

## 📁 项目结构

```
ai_batch_generation_website/
├── server/                      # FastAPI 后端
│   ├── app.py                   # 主应用
│   ├── db.py                    # 数据库
│   ├── models.py                # ORM 模型
│   ├── schemas.py               # Pydantic 数据验证
│   ├── security.py              # 认证与安全
│   ├── queue.py                 # 任务队列
│   ├── settings.py              # 配置
│   ├── crypto.py                # 加密工具
│   ├── providers/               # AI 服务提供商
│   │   ├── types.py
│   │   ├── yunwu.py
│   │   └── yunwu_client.py
│   ├── batch_utils.py
│   ├── cleanup.py
│   └── rate_limit.py
├── public/                      # 前端资源
│   └── index.html               # 单页应用
├── deploy/                      # 部署脚本
│   └── setup_zuoshipin_server.sh  # 生产部署脚本
├── colab_webapp_ngrok.ipynb     # Colab Notebook (ngrok)
├── colab_webapp_cloudflare.ipynb # Colab Notebook (Cloudflare)
├── add_user.py                  # 用户管理脚本
├── adjust_credits.py            # 积分调整脚本
├── list_users.py                # 用户列表脚本
├── requirements.txt             # Python 依赖
└── README.md                    # 本文件
```

---

## 🔐 用户管理

### 默认管理员

- 首次启动会自动创建管理员账号 `admin`。
- 管理员初始密码由环境变量 `INITIAL_ADMIN_PASSWORD` 指定，默认值仅用于开发：`admin000`。
- 生产环境务必设置 `INITIAL_ADMIN_PASSWORD` 或在首次登录后立即修改密码。

### 添加新用户

```bash
# 创建普通用户
python add_user.py username password

# 创建管理员
python add_user.py username password --admin

# 创建用户后设置积分（使用积分工具）
python manage_credits.py add username +100 充值
```

### 调整用户积分

```bash
# 增加积分
python adjust_credits.py username 50 "充值"

# 减少积分
python adjust_credits.py username -20 "消费退款"
```

---

## 🔗 API 端点

### 认证
- `POST /api/login` - 用户登录
- `POST /api/logout` - 用户登出
- `GET /api/me` - 获取当前用户信息（含积分）

### 视频生成
- `POST /api/batches` - 创建批次（自动扣除积分）
- `GET /api/batches` - 获取批次列表（分页）
- `GET /api/batches/{id}/tasks` - 获取批次任务
- `DELETE /api/batches/{id}` - 删除批次

### 文件处理
- `POST /api/images/upload` - 上传图片
- `DELETE /api/images` - 删除图片
- `GET /api/batches/{id}/download` - 下载 ZIP（自动下载远程视频）

### 任务操作
- `POST /api/tasks/{id}/retry` - 重试任务（失败退款）
- `POST /api/tasks/{id}/cancel` - 取消任务
- `DELETE /api/tasks/{id}` - 删除任务

### 管理员
- `POST /api/admin/credits/adjust` - 调整用户积分

---

## ⚙️ 环境变量

| 变量 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `YUNWU_API_KEY` | Yunwu API 密钥 | ✅ | - |
| `PUBLIC_BASE_URL` | 公网访问地址 | ✅ | - |
| `DATABASE_URL` | 数据库 URL | ❌ | `sqlite:///app.db` |
| `UPLOAD_DIR` | 图片上传目录 | ❌ | `./uploads` |
| `DISABLE_BACKGROUND` | 禁用后台任务 | ❌ | `false` |
| `CRYPTO_SECRET` | 加密密钥（32字节） | ❌ | 自动生成 |

**生产环境**: 使用 `.env` 文件或 systemd `EnvironmentFile`。

---

## 🛠️ 技术栈

### 后端
- **FastAPI** - 现代 Web 框架
- **SQLAlchemy** - ORM
- **SQLite** - 数据库（可迁移到 PostgreSQL）
- **bcrypt** - 密码加密
- **cryptography** - 数据加密
- **uvicorn** - ASGI 服务器

### 前端
- **HTML5** - 标记语言
- **CSS3** - 样式
- **Vanilla JavaScript** - 交互

### 部署
- **systemd** - 服务管理
- **Nginx** - 反向代理
- **Cloudflare** - DNS/CDN/SSL
- **Google Colab** - 云端测试

---

## 📊 工作流

### 用户操作流程

```
1. 登录
   ↓
2. 上传图片
   ↓
3. 输入 Prompt (≤3000 字符)
   ↓
4. 配置参数(模型、方向、尺寸、时长、数量)
   ↓
5. 创建批次（自动扣除积分）
   ↓
6. 监控进度(实时更新)
   ↓
7. 查看结果 & 下载 ZIP
```

### 后端任务流程

```
创建批次
   ↓
验证参数 & 检查积分
   ↓
扣除积分
   ↓
生成任务
   ↓
加入队列
   ↓
后台执行
   ├─ 上传图片到 Yunwu
   ├─ 调用 Sora 2 API
   ├─ 轮询结果
   └─ 保存视频链接
   ↓
更新任务状态
   ├─ 成功: 保存结果
   └─ 失败: 自动退款
```

---

## 🔒 安全特性

- ✅ 密码使用 bcrypt 加密
- ✅ API 密钥加密存储（Fernet）
- ✅ 用户数据隔离
- ✅ 会话管理
- ✅ 速率限制（防刷）
- ✅ 防火墙配置（ufw）
- ✅ 入侵检测（fail2ban）

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎提交 Pull Request!

```bash
1. Fork 本仓库
2. 创建特性分支 (git checkout -b feature/AmazingFeature)
3. 提交更改 (git commit -m 'Add some AmazingFeature')
4. 推送到分支 (git push origin feature/AmazingFeature)
5. 开启 Pull Request
```

---

## 📞 联系方式

- GitHub: https://github.com/ge0rgeguo/batch_ai_video
- 问题报告: https://github.com/ge0rgeguo/batch_ai_video/issues

---

## 🎯 路线图

- [ ] 添加更多 AI 模型支持
- [ ] 实现 API Key 管理界面
- [ ] 支持 PostgreSQL 数据库
- [ ] WebSocket 实时更新
- [ ] 导出为 CSV 报表
- [ ] 国际化支持

---

**祝你使用愉快!** 🚀

如有问题或建议，欢迎开启 Issue 或提交 PR。
