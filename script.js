// 日记数据存储键
const STORAGE_KEY = 'lightweightDiary';

// DOM 元素
const titleInput = document.getElementById('titleInput');
const contentInput = document.getElementById('contentInput');
const saveBtn = document.getElementById('saveBtn');
const clearBtn = document.getElementById('clearBtn');
const clearAllBtn = document.getElementById('clearAllBtn');
const diaryEntries = document.getElementById('diaryEntries');

// 加载日记列表
function loadDiaries() {
    const diaries = getDiaries();
    renderDiaries(diaries);
}

// 从本地存储获取日记
function getDiaries() {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
}

// 保存日记到本地存储
function saveDiaries(diaries) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(diaries));
}

// 渲染日记列表
function renderDiaries(diaries) {
    if (diaries.length === 0) {
        diaryEntries.innerHTML = '<div class="empty-state">还没有日记，开始写第一篇吧！</div>';
        return;
    }

    diaryEntries.innerHTML = '';
    
    // 按时间倒序排列
    const sortedDiaries = [...diaries].sort((a, b) => b.timestamp - a.timestamp);
    
    sortedDiaries.forEach(diary => {
        const entryDiv = createDiaryElement(diary);
        diaryEntries.appendChild(entryDiv);
    });
}

// 创建日记元素
function createDiaryElement(diary) {
    const entryDiv = document.createElement('div');
    entryDiv.className = 'diary-entry';
    
    const date = new Date(diary.timestamp);
    const dateStr = formatDate(date);
    
    const title = diary.title || '无标题';
    
    entryDiv.innerHTML = `
        <div class="entry-header">
            <div class="entry-title">${escapeHtml(title)}</div>
            <div class="entry-date">${dateStr}</div>
        </div>
        <div class="entry-content">${escapeHtml(diary.content)}</div>
        <div class="entry-actions">
            <button class="btn btn-danger btn-small delete-btn" data-id="${diary.id}">删除</button>
        </div>
    `;
    
    // 添加删除按钮事件
    const deleteBtn = entryDiv.querySelector('.delete-btn');
    deleteBtn.addEventListener('click', () => deleteDiary(diary.id));
    
    return entryDiv;
}

// 格式化日期
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 保存新日记
function saveDiary() {
    const title = titleInput.value.trim();
    const content = contentInput.value.trim();
    
    if (!content) {
        showNotification('请输入日记内容！');
        return;
    }
    
    const diary = {
        id: generateUniqueId(),
        title: title,
        content: content,
        timestamp: Date.now()
    };
    
    const diaries = getDiaries();
    diaries.push(diary);
    saveDiaries(diaries);
    
    // 清空输入框
    titleInput.value = '';
    contentInput.value = '';
    
    // 重新加载列表
    loadDiaries();
    
    // 显示成功提示
    showNotification('日记保存成功！');
}

// 生成唯一ID
function generateUniqueId() {
    // 使用时间戳和随机数组合生成唯一ID
    return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}

// 删除日记
async function deleteDiary(id) {
    const confirmed = await showConfirm('确定要删除这篇日记吗？');
    if (!confirmed) {
        return;
    }
    
    let diaries = getDiaries();
    diaries = diaries.filter(diary => diary.id !== id);
    saveDiaries(diaries);
    loadDiaries();
    
    showNotification('日记已删除');
}

// 清空输入框
function clearInputs() {
    titleInput.value = '';
    contentInput.value = '';
    contentInput.focus();
}

// 清空所有日记
async function clearAllDiaries() {
    const confirmed = await showConfirm('确定要删除所有日记吗？此操作无法撤销！');
    if (!confirmed) {
        return;
    }
    
    localStorage.removeItem(STORAGE_KEY);
    loadDiaries();
    
    showNotification('所有日记已清空');
}

// 显示通知
function showNotification(message) {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        z-index: 1000;
        animation: slideInNotification 0.3s ease-out;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // 3秒后移除
    setTimeout(() => {
        notification.style.animation = 'slideOutNotification 0.3s ease-out';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// 显示确认对话框
function showConfirm(message) {
    return new Promise((resolve) => {
        // 创建模态框覆盖层
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        // 创建模态框内容
        const modal = document.createElement('div');
        modal.className = 'modal-content';
        modal.innerHTML = `
            <div class="modal-title">确认操作</div>
            <div class="modal-message">${escapeHtml(message)}</div>
            <div class="modal-buttons">
                <button class="btn btn-secondary modal-cancel">取消</button>
                <button class="btn btn-danger modal-confirm">确定</button>
            </div>
        `;
        
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        // 取消按钮
        const cancelBtn = modal.querySelector('.modal-cancel');
        cancelBtn.addEventListener('click', () => {
            overlay.remove();
            resolve(false);
        });
        
        // 确定按钮
        const confirmBtn = modal.querySelector('.modal-confirm');
        confirmBtn.addEventListener('click', () => {
            overlay.remove();
            resolve(true);
        });
        
        // 点击覆盖层关闭
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.remove();
                resolve(false);
            }
        });
    });
}

// 事件监听
saveBtn.addEventListener('click', saveDiary);
clearBtn.addEventListener('click', clearInputs);
clearAllBtn.addEventListener('click', clearAllDiaries);

// 回车保存（Ctrl+Enter）
contentInput.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        saveDiary();
    }
});

// 页面加载时加载日记列表
document.addEventListener('DOMContentLoaded', loadDiaries);
