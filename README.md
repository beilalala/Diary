# 轻量日程管理（本地版）

这是一个轻量的个人日程管理工具，默认使用 `Tkinter` 桌面界面（`main.py`），数据保存在本地 `data/storage.json`。

## 快速运行（Windows，推荐 PowerShell）

1. 打开 PowerShell，进入工程目录：

```powershell
cd "c:\Users\wjt99\Desktop\小游戏"
```

2. 创建并激活虚拟环境（可选但推荐）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
# 或在 cmd 中： .\.venv\Scripts\activate
```

3. 运行桌面程序（Tkinter，无额外依赖）：

```powershell
python main.py
```

程序窗口会弹出，界面包含“周视图 / 月视图 / 往期回顾”，可添加、编辑、删除日程，数据保存在 `data/storage.json`。

## 可选：Web 版本（Streamlit），方便部署并获取网址

已提供一个简化的 Streamlit 示例 `web_app.py`，可本地运行或部署到 Streamlit Community Cloud 获取公网网址。

本地运行：

```powershell
# 激活虚拟环境后
pip install -r requirements.txt
streamlit run web_app.py
```

打开浏览器访问默认地址（如 http://localhost:8501）。

部署到 Streamlit Community Cloud（获取网址）：

- 将仓库推到 GitHub（公开或私有都支持）。
- 在 https://share.streamlit.io 登录并新建应用，连接到你的 GitHub 仓库并选择 `web_app.py` 作为入口文件。
- 部署完成后 Streamlit 会分配一个公网 URL，直接打开即可使用。

如果你希望我代为：
- 将仓库初始化为 Git 并推送到你的 GitHub（需你提供仓库权限或添加我为 collaborator），或
- 生成完整的 GitHub Actions / 部署配置并指导你一步步完成部署，
请告诉我你更愿意哪种方式，我可以继续代劳或给出详细步骤。

## 提示与注意

- 数据文件：`data/storage.json`（请勿随意删除）。
- 桌面版为纯本地应用，不会联网。Web 版如果部署到云端则会将存储文件随着仓库或云端持久化，若要保持私密请不要部署到公共平台或使用加密/私有存储方案。

---
文件：`main.py`（桌面 Tkinter 程序），`web_app.py`（Streamlit 示例），`data/storage.json`（数据文件），`requirements.txt`（Web 版依赖）。