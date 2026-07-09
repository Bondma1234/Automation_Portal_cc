/* 设备管理：品牌台架卡片（在线状态 / udid / 分辨率 / 系统 / 代理就绪），可刷新。 */
import { api } from '../api.js';
import { root, phead, btn, badge } from '../ui.js';
import { go } from '../router.js';

export async function render() {
  const devices = await api.get('/api/devices');
  const cards = devices.map((d) => '<div class="card">'
    + `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;"><span style="font-weight:500;font-size:13px;color:var(--color-text-primary);">${d.name}</span>${d.online ? badge('b-ok', '在线') : badge('b-fail', '离线')}</div>`
    + '<table style="width:100%;font-size:12px;color:var(--color-text-secondary);">'
    + `<tr><td style="padding:2px 0;">udid</td><td style="text-align:right;font-family:var(--font-mono);font-size:11px;color:var(--color-text-primary);">${d.udid}</td></tr>`
    + `<tr><td style="padding:2px 0;">分辨率</td><td style="text-align:right;color:var(--color-text-primary);">${d.resolution}</td></tr>`
    + `<tr><td style="padding:2px 0;">系统</td><td style="text-align:right;color:var(--color-text-primary);">${d.os}</td></tr>`
    + `<tr><td style="padding:2px 0;">代理</td><td style="text-align:right;">${d.agent_ready ? badge('b-ok', '就绪') : badge('b-mut', '未连接')}</td></tr>`
    + '</table></div>').join('');
  return phead('设备管理', '品牌台架在线状态与设备代理就绪情况', btn('刷新', 'ti-refresh', 0, 'devRefresh'))
    + `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:10px;">${cards}</div>`;
}

export function init() {
  root().querySelector('#devRefresh').addEventListener('click', () => go('devices'));
}
