/* UI 工具层：与原型同名的 HTML 片段工厂 + toast / modal。
   所有片段的类名与内联样式照搬原型，是「观感一致」的公共基础，改动需对照原型。 */

export const root = () => document.querySelector('.jdo');

/** 状态徽标 */
export function badge(cls, text) { return `<span class="badge ${cls}">${text}</span>`; }

/** 页头：标题 + 副标题 + 右侧动作区 */
export function phead(title, sub, actions) {
  return `<div class="phead"><div><div class="ptitle">${title}</div>${sub ? `<div class="psub">${sub}</div>` : ''}</div><div>${actions || ''}</div></div>`;
}

/** 指标卡：标签 + 数值 + 右上角图标（col 可指定数值颜色） */
export function mcard(label, num, icon, col) {
  return `<div class="mcard"><div style="display:flex;justify-content:space-between;align-items:center;"><span class="mlab">${label}</span><i class="ti ${icon}" style="color:var(--color-text-tertiary);font-size:15px;" aria-hidden="true"></i></div><div class="mnum"${col ? ` style="color:${col}"` : ''}>${num}</div></div>`;
}

/** 按钮：primary=1 主按钮 / 0 次按钮 */
export function btn(text, icon, primary, id) {
  return `<button class="${primary ? 'pbtn' : 'gbtn'}"${id ? ` id="${id}"` : ''}><i class="ti ${icon}" style="vertical-align:-2px;" aria-hidden="true"></i> ${text}</button>`;
}

/** 统计 chip（报告详情用） */
export function chip(label, value) { return `<span class="chip">${label}<b>${value}</b></span>`; }

/** select 选项（保持当前选中态） */
export function opt(v, cur) { return `<option${v === cur ? ' selected' : ''}>${v}</option>`; }

/** 底部浮出的轻提示，1.9s 自动消失（样式与原型一致） */
export function toast(msg) {
  const frame = root().querySelector('#frame');
  const t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = 'position:absolute;left:50%;bottom:16px;transform:translateX(-50%);background:var(--color-text-primary);color:var(--color-background-primary);font-size:12px;padding:8px 15px;border-radius:var(--border-radius-md);z-index:90;opacity:0;transition:opacity .2s;box-shadow:0 2px 12px rgba(0,0,0,0.3);';
  frame.appendChild(t);
  requestAnimationFrame(() => { t.style.opacity = '1'; });
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 250); }, 1900);
}

/** 弹窗标题行（含右上角关闭按钮 #mdX） */
export function mdHead(title) {
  return `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:13px;"><span style="font-weight:500;font-size:15px;color:var(--color-text-primary);">${title}</span><button id="mdX" class="iconbtn" aria-label="关闭"><i class="ti ti-x" aria-hidden="true"></i></button></div>`;
}

/** 模态弹窗：遮罩点击/右上角 X/#mdCancel 均可关闭；返回遮罩元素供绑定内部事件 */
export function openModal(html, width) {
  const ov = document.createElement('div');
  ov.style.cssText = 'position:absolute;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:50;padding:14px;';
  ov.innerHTML = `<div style="background:var(--color-background-primary);border:0.5px solid var(--color-border-secondary);border-radius:var(--border-radius-lg);width:${width || 380}px;max-width:100%;max-height:100%;overflow:auto;padding:16px 18px;">${html}</div>`;
  root().querySelector('#frame').appendChild(ov);
  ov.addEventListener('click', (e) => { if (e.target === ov) ov.remove(); });
  const x = ov.querySelector('#mdX');
  if (x) x.addEventListener('click', () => ov.remove());
  const c = ov.querySelector('#mdCancel');
  if (c) c.addEventListener('click', () => ov.remove());
  return ov;
}

/** 图标按钮短暂变 ✓（下载成功反馈，与原型一致） */
export function flash(button) {
  const old = button.innerHTML;
  button.innerHTML = '<i class="ti ti-check" aria-hidden="true"></i>';
  button.style.color = 'var(--color-text-success)';
  setTimeout(() => { button.innerHTML = old; button.style.color = ''; }, 1200);
}
