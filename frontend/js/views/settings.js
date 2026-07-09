/* 系统设置：失败通知（Webhook + 推送策略，修改即保存）+ 成员与角色。 */
import { api } from '../api.js';
import { root, phead } from '../ui.js';

let settings = null;
let members = [];

export async function render() {
  [settings, members] = await Promise.all([api.get('/api/settings'), api.get('/api/members')]);
  const memberRows = members.map((m) => `<tr class="hov"><td>${m.name}</td><td class="sub">${m.role}</td></tr>`).join('');
  return phead('系统设置', '失败通知与成员权限')
    + '<div class="card" style="margin-bottom:11px;"><div style="font-weight:500;font-size:13px;margin-bottom:9px;color:var(--color-text-primary);">失败通知</div>'
    + '<label class="sub">企业微信 / 钉钉 Webhook</label>'
    + `<input id="stWebhook" type="text" value="${settings.webhook}" style="width:100%;margin:5px 0 11px;font-size:12px;">`
    + `<label style="font-size:12.5px;display:flex;align-items:center;gap:6px;color:var(--color-text-primary);"><input id="stFail" type="checkbox"${settings.notify_fail ? ' checked' : ''}> 用例失败时实时推送</label>`
    + `<label style="font-size:12.5px;display:flex;align-items:center;gap:6px;margin-top:5px;color:var(--color-text-primary);"><input id="stDaily" type="checkbox"${settings.notify_daily ? ' checked' : ''}> 每日回归汇总报告</label></div>`
    + `<div class="card"><div style="font-weight:500;font-size:13px;margin-bottom:9px;color:var(--color-text-primary);">成员</div><table class="tbl"><tbody>${memberRows}</tbody></table></div>`;
}

export function init() {
  const el = root();
  // 任一项变更即静默保存（界面与原型一致，无需保存按钮）
  const save = () => api.put('/api/settings', {
    webhook: el.querySelector('#stWebhook').value.trim(),
    notify_fail: el.querySelector('#stFail').checked,
    notify_daily: el.querySelector('#stDaily').checked,
  }).catch(() => { /* 保存失败不打断浏览，下次进入时以后端为准 */ });
  el.querySelector('#stWebhook').addEventListener('change', save);
  el.querySelector('#stFail').addEventListener('change', save);
  el.querySelector('#stDaily').addEventListener('change', save);
}
