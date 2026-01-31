# 📔 轻量日记

王俊腾的家

## 简介

这是一个轻量级的在线日记应用，使用纯HTML、CSS和JavaScript开发，无需后端服务器，所有数据保存在浏览器本地存储中。

## 功能特点

- ✍️ 简洁的日记编写界面
- 💾 自动保存到浏览器本地存储
- 📝 支持标题和内容
- 🗑️ 删除单篇或全部日记
- 📱 响应式设计，支持移动设备
- 🎨 精美的渐变色设计
- ⚡ 快捷键支持（Ctrl+Enter保存）

## 使用方法

1. 直接在浏览器中打开 `index.html` 文件
2. 或者通过任何Web服务器访问该目录

### 使用Python快速启动

```bash
# Python 3
python -m http.server 8000

# 然后在浏览器访问 http://localhost:8000
```

### 使用Node.js快速启动

```bash
# 安装 http-server
npm install -g http-server

# 启动服务器
http-server

# 然后在浏览器访问显示的地址
```

## 技术栈

- HTML5
- CSS3
- JavaScript (ES6+)
- LocalStorage API

## 数据存储

所有日记数据都保存在浏览器的本地存储（LocalStorage）中，不会上传到任何服务器，确保您的隐私安全。

## 浏览器兼容性

支持所有现代浏览器：
- Chrome/Edge (推荐)
- Firefox
- Safari
- Opera

## 许可

MIT License
