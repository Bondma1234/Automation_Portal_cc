/* 工作台：指标卡 + 最近执行 + 快捷入口（数据来自 /api/dashboard，布局与原型一致）。 */
import { api } from '../api.js';
import { root, phead, mcard, btn, badge } from '../ui.js';
import { go } from '../router.js';
import { openUpload } from './scripts.js';
import { openNewTask } from './tasks.js';

export async function render() {
  const d = await api.get('/api/dashboard');
  const rows = d.recent.map((r) => `<tr class="hov"><td>${r.task}</td><td>${r.brand}</td><td>${r.status === '通过' ? badge('b-ok', '通过') : badge('b-fail', '失败')}</td><td class="sub">${r.time}</td></tr>`).join('');
  return phead('工作台', '平台整体运行概览')
    + '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:10px;margin-bottom:15px;">'
    + mcard('业务用例覆盖率', d.coverage + '%', 'ti-chart-pie', 'var(--color-text-success)')
    + mcard('今日执行', d.today_runs + ' 次', 'ti-player-play')
    + mcard('执行成功率', d.success_rate + '%', 'ti-circle-check')
    + mcard('在线设备', d.devices, 'ti-devices')
    + '</div>'
    + '<div class="card" style="margin-bottom:12px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;"><span style="font-weight:500;font-size:13px;color:var(--color-text-primary);">最近执行</span><span id="dashAll" class="sub lnk">查看全部 ›</span></div>'
    + `<table class="tbl"><tbody>${rows}</tbody></table></div>`
    + `<div style="display:flex;gap:10px;">${btn('新建测试任务', 'ti-plus', 1, 'dashNew')}${btn('上传脚本', 'ti-upload', 0, 'dashUp')}</div>`;
}

export function init() {
  const el = root();
  el.querySelector('#dashUp').addEventListener('click', openUpload);
  el.querySelector('#dashNew').addEventListener('click', openNewTask);
  el.querySelector('#dashAll').addEventListener('click', () => go('reports'));
}
