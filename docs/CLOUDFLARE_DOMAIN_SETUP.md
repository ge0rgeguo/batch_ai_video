# Cloudflare 域名关联指南

## 📋 前提条件

- 已购买域名 `zuoshipin.net`（在阿里云）
- 已有阿里云 ECS 服务器（知道公网 IP）
- 已有 Cloudflare 账号（免费即可）

---

## 🔧 详细步骤

### 步骤 1: 在 Cloudflare 添加域名

1. 访问 https://dash.cloudflare.com 登录
2. 点击右上角 **"Add a Site"**
3. 输入 `zuoshipin.net`，点击 **"Add site"**
4. 选择 **Free** 计划（免费），点击 **"Continue"**
5. Cloudflare 会自动扫描现有 DNS 记录

### 步骤 2: 修改域名 DNS 服务器（关键步骤）

Cloudflare 会显示两个 DNS 服务器地址，例如：
```
nameserver1.cloudflare.com (例如: elin.ns.cloudflare.com)
nameserver2.cloudflare.com (例如: luke.ns.cloudflare.com)
```

**在阿里云操作**：
1. 登录阿里云控制台 → **域名** → **域名列表**
2. 找到 `zuoshipin.net`，点击 **"解析"** 或 **"DNS设置"**
3. 点击 **"修改 DNS 服务器"** 或 **"DNS修改"**
4. 删除原有的 DNS 服务器（阿里云默认的）
5. 添加 Cloudflare 提供的两个 nameserver
6. 点击 **"确认"** 保存

⚠️ **重要**：DNS 切换需要时间（通常 5 分钟到 2 小时），期间域名可能无法访问。

### 步骤 3: 在 Cloudflare 配置 DNS 记录

1. 返回 Cloudflare 控制台，进入 `zuoshipin.net` 站点
2. 点击左侧 **"DNS"** → **"Records"**
3. 删除 Cloudflare 自动创建的记录（如果有）
4. 点击 **"Add record"**，添加：

   **主域名记录**：
   ```
   类型: A
   名称: @ (或留空)
   内容: [你的阿里云服务器公网 IP，例如: 47.xx.xx.xx]
   代理状态: 🟠 Proxied (橙色云朵，必须开启！)
   TTL: Auto
   ```
   点击 **"Save"**

   **www 子域名（可选）**：
   ```
   类型: A
   名称: www
   内容: [同样的服务器 IP]
   代理状态: 🟠 Proxied (橙色云朵)
   TTL: Auto
   ```
   点击 **"Save"**

### 步骤 4: 配置 SSL/TLS（重要）

1. 在 Cloudflare 控制台，点击左侧 **"SSL/TLS"**
2. 找到 **"Overview"** 标签页
3. **加密模式** 选择：**Full (strict)**
   - ✅ **Full (strict)**: Cloudflare ↔ 源站都使用 HTTPS（推荐）
   - ⚠️ **Full**: 允许自签名证书
   - ❌ **Flexible**: 仅 Cloudflare 到用户是 HTTPS（不安全，不推荐）

### 步骤 5: 生成并上传 Cloudflare Origin 证书（推荐）

如果需要源站使用 HTTPS（部署脚本会自动检测）：

1. 在 Cloudflare 控制台，点击 **"SSL/TLS"** → **"Origin Server"**
2. 点击 **"Create Certificate"**
3. 配置：
   - **Private key type**: RSA (2048)
   - **Hostnames**: 
     ```
     zuoshipin.net
     *.zuoshipin.net
     ```
   - **Certificate Validity**: 选择最长的（15 年）
4. 点击 **"Create"**
5. 复制证书内容（`.crt` 文件）和私钥（`.key` 文件）

**上传到服务器**：
```bash
# 在服务器上执行
sudo mkdir -p /etc/ssl/origin
sudo nano /etc/ssl/origin/cf-origin.crt
# 粘贴证书内容，保存退出（Ctrl+X, Y, Enter）

sudo nano /etc/ssl/origin/cf-origin.key
# 粘贴私钥内容，保存退出

sudo chmod 600 /etc/ssl/origin/cf-origin.*
```

### 步骤 6: 验证配置

**等待 DNS 生效**（5-30 分钟）

**检查 DNS 解析**：
```bash
# 检查 DNS 服务器是否指向 Cloudflare
dig zuoshipin.net NS

# 应该看到类似：
# zuoshipin.net.  3600  IN  NS  elin.ns.cloudflare.com.
# zuoshipin.net.  3600  IN  NS  luke.ns.cloudflare.com.

# 检查 A 记录（应该显示 Cloudflare 的 IP，不是你的服务器 IP）
dig zuoshipin.net A

# 检查代理是否生效（应该显示 Cloudflare IP）
curl -I https://zuoshipin.net
```

**测试访问**：
- 浏览器访问：`https://zuoshipin.net`
- 应该看到你的网站或 Nginx 默认页面

---

## ✅ 检查清单

- [ ] 域名已添加到 Cloudflare
- [ ] DNS 服务器已改为 Cloudflare 提供的地址
- [ ] 在 Cloudflare 添加了 A 记录（@ 和 www）指向服务器 IP
- [ ] **开启了橙色云朵（Proxied）** ← 最重要！
- [ ] SSL/TLS 模式设置为 **Full (strict)**
- [ ] Cloudflare Origin 证书已上传到服务器（如需要）
- [ ] 服务器防火墙已放行 80/443 端口
- [ ] Nginx 已配置并运行

---

## 🐛 常见问题排查

### 1. DNS 不生效

**症状**：访问域名显示 "无法访问此网站"

**解决**：
```bash
# 检查 DNS 服务器
dig zuoshipin.net NS

# 如果还是显示阿里云的 DNS，等待更长时间（最多 48 小时）
# 或者检查阿里云域名控制台是否正确配置
```

### 2. 502 Bad Gateway

**症状**：访问域名显示 "502 Bad Gateway"

**原因**：Cloudflare 无法连接到你的服务器

**排查**：
```bash
# 1. 检查服务器是否运行
sudo systemctl status ai-batch

# 2. 检查 Nginx 是否正常
sudo nginx -t
sudo systemctl status nginx

# 3. 检查防火墙
sudo ufw status
# 确保 80/443 已开放

# 4. 检查服务器日志
sudo journalctl -u ai-batch -n 50
sudo tail -f /var/log/nginx/error.log

# 5. 测试本地访问
curl http://127.0.0.1:8888
```

### 3. SSL 证书错误

**症状**：浏览器显示 "不安全连接" 或证书错误

**解决**：
- 确认 Cloudflare SSL/TLS 模式为 **Full (strict)**
- 确认服务器已上传 Cloudflare Origin 证书
- 确认 Nginx 配置正确引用证书路径

### 4. 域名解析到错误的 IP

**症状**：`dig zuoshipin.net A` 显示的不是 Cloudflare IP

**解决**：
- 确认开启了 **橙色云朵（Proxied）**
- 如果显示的是你的服务器 IP，说明代理未开启

---

## 📞 需要帮助？

如果遇到问题，请提供：
1. `dig zuoshipin.net NS` 的输出
2. `dig zuoshipin.net A` 的输出
3. 服务器公网 IP（脱敏后）
4. Cloudflare SSL/TLS 模式截图
5. 错误信息截图

