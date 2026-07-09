/* 定时调度：回归计划卡片 + 启停开关（切换即持久化到后端）。 */
import { api } from '../api.js';
import { root, phead, btn } from '../ui.js';

export async function render() {
  const jobs = await api.get('/api/schedules');
  const cards = jobs.map((j) => '<div class="card" style="display:flex;align-items:center;gap:12px;">'
    + `<div style="flex:1;"><div style="font-weight:500;font-size:13px;color:var(--color-text-primary);">${j.name}</div>`
    + `<div class="sub" style="margin-top:3px;"><i class="ti ti-clock" style="vertical-align:-2px;font-size:13px;" aria-hidden="true"></i> ${j.cron_label} · ${j.scope_label}</div>`
    + `<div class="sub" style="margin-top:1px;">下次：${j.next_time}</div></div>`
    + `<div class="sw${j.enabled ? ' on' : ''}" data-id="${j.id}" role="switch" aria-label="启停 ${j.name}"></div></div>`).join('');
  return phead('定时调度', '自动触发回归，开关可切换启停', btn('新建计划', 'ti-plus', 1))
    + `<div style="display:flex;flex-direction:column;gap:9px;">${cards}</div>`;
}

export function init() {
  root().querySelectorAll('.sw').forEach((sw) => {
    sw.addEventListener('click', async () => {
      sw.classList.toggle('on');   // 先即时反馈（与原型手感一致），后端失败再回滚
      try {
        const res = await api.post(`/api/schedules/${sw.dataset.id}/toggle`);
        sw.classList.toggle('on', res.enabled);
      } catch (e) {
        sw.classList.toggle('on');
      }
    });
  });
}
