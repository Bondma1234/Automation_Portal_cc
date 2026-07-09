/* 报告中心：日期/App/品牌/状态筛选 + 查询 + 导出；点击行展开详情
   （统计 chip + 用例结果列表 + 失败用例现场 + Allure 入口），布局与原型一致。 */
import { api } from '../api.js';
import { root, phead, btn, badge, chip, opt, toast } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

function filterQuery() {
  const f = store.repFilter;
  return `date_from=${f.from}&date_to=${f.to}&app=${encodeURIComponent(f.app)}&brand=${encodeURIComponent(f.brand)}&status=${encodeURIComponent(f.status)}`;
}

export async function render() {
  const f = store.repFilter;
  const reports = await api.get(`/api/reports?${filterQuery()}`);

  const appOpts = opt('全部 App', f.app) + store.meta.apps.map((a) => opt(a, f.app)).join('');
  const brOpts = opt('全部品牌', f.brand) + store.meta.brands.map((b) => opt(b, f.brand)).join('');
  const stOpts = ['全部状态', '通过', '失败'].map((v) => opt(v, f.status)).join('');

  // 筛选控件统一样式：与测试用例一致（34px 高 / 13px 字），协调美观
  const ctl = 'height:34px;font-size:13px;padding:0 10px;border-radius:var(--border-radius-md);';
  const toolbar = '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;">'
    + `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;"><input id="rFrom" type="date" value="${f.from}" style="${ctl}width:150px;"><span class="sub">到</span><input id="rTo" type="date" value="${f.to}" style="${ctl}width:150px;"><select id="rApp" style="${ctl}width:120px;">${appOpts}</select><select id="rBrand" style="${ctl}width:110px;">${brOpts}</select><select id="rStatus" style="${ctl}width:110px;">${stOpts}</select>${btn('查询', 'ti-search', 1, 'rQuery')}</div>`
    + `<div>${btn('导出 Excel', 'ti-file-export', 0, 'rExport')}</div></div>`;

  let body = reports.length ? '' : '<tr><td colspan="8" class="sub" style="text-align:center;padding:18px;">无匹配报告</td></tr>';
  reports.forEach((r, i) => {
    body += `<tr class="rprow hov" data-i="${i}" style="cursor:pointer;"><td>#${r.id}</td><td>${r.task}</td><td>${r.brand}</td><td>${r.pass}/${r.total}</td><td class="sub">${r.dur}</td><td>${r.status === '通过' ? badge('b-ok', '通过') : badge('b-fail', '失败')}</td><td class="sub">${r.time.slice(5)}</td><td style="text-align:right;"><button class="iconbtn alBtn" data-id="${r.id}" title="打开 Allure" aria-label="打开 Allure" style="width:auto;padding:0 8px;gap:4px;"><i class="ti ti-external-link" aria-hidden="true"></i> Allure</button></td></tr>`;
    body += `<tr class="rpdet" data-i="${i}" style="display:none;"><td colspan="8" style="padding:4px 7px 10px;">${detail(r)}</td></tr>`;
  });

  return phead('报告中心', '按时间 / App / 品牌 / 状态筛选，点击行展开详情', `<span class="sub">共 ${reports.length} 条</span>`)
    + toolbar
    + `<table class="tbl"><thead><tr><th>编号</th><th>任务</th><th>品牌</th><th>通过</th><th>耗时</th><th>结果</th><th>时间</th><th style="text-align:right;">报告</th></tr></thead><tbody>${body}</tbody></table>`;
}

/** 行展开详情：统计 chip + 用例结果表 + 失败用例的日志/截图/录屏占位（与原型一致） */
function detail(r) {
  const fails = r.total - r.pass;
  const head = '<div style="display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:10px;">'
    + chip('通过 ', `<span style="color:var(--color-text-success)">${r.pass}</span>`)
    + chip('失败 ', `<span style="color:var(--color-text-danger)">${fails}</span>`)
    + chip('耗时 ', r.dur) + chip('设备 ', `${r.brand}台架`) + chip('触发 ', r.trigger_type)
    + `<button class="iconbtn alBtn" data-id="${r.id}" style="width:auto;padding:0 10px;gap:4px;margin-left:auto;border-color:var(--color-border-info);color:var(--color-text-info);"><i class="ti ti-external-link" aria-hidden="true"></i> 打开 Allure</button></div>`;

  const rows = r.cases.map((c) => {
    let line = `<tr><td style="font-family:var(--font-mono);font-size:11px;">${c.case_id}</td><td>${c.name}</td><td>${c.result === 'ok' ? badge('b-ok', '通过') : badge('b-fail', '失败')}</td></tr>`;
    if (c.result === 'fail') {
      // 失败现场三件套占位（截图/录屏/logcat），接 Allure 后替换为真实附件
      line += '<tr><td colspan="3" style="padding:0 7px 8px;"><div style="background:var(--color-background-tertiary);border-radius:6px;padding:8px 11px;font-family:var(--font-mono);font-size:11px;line-height:1.7;color:var(--color-text-secondary);">› 校验 media_session 状态 … 期望 PLAYING，实际 PAUSED ✗<br><span style="color:var(--color-text-danger);">AssertionError: 播放未生效（疑似登录态失效）</span><div style="display:flex;gap:8px;margin-top:8px;"><div style="width:84px;height:50px;background:var(--color-background-secondary);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--color-text-tertiary);"><i class="ti ti-photo" aria-hidden="true"></i></div><div style="width:84px;height:50px;background:var(--color-background-secondary);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--color-text-tertiary);"><i class="ti ti-video" aria-hidden="true"></i></div><div style="width:84px;height:50px;background:var(--color-background-secondary);border-radius:4px;display:flex;align-items:center;justify-content:center;color:var(--color-text-tertiary);"><i class="ti ti-file-text" aria-hidden="true"></i></div></div></div></td></tr>';
    }
    return line;
  }).join('');
  const more = r.total > r.cases.length ? `<tr><td colspan="3" class="sub" style="text-align:center;">… 共 ${r.total} 条用例</td></tr>` : '';

  return `<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:11px 13px;">${head}<table class="tbl"><thead><tr><th>用例编号</th><th>用例</th><th>结果</th></tr></thead><tbody>${rows}${more}</tbody></table></div>`;
}

export function init() {
  const el = root();
  el.querySelector('#rQuery').addEventListener('click', () => {
    store.repFilter = {
      from: el.querySelector('#rFrom').value, to: el.querySelector('#rTo').value,
      app: el.querySelector('#rApp').value, brand: el.querySelector('#rBrand').value,
      status: el.querySelector('#rStatus').value,
    };
    go('reports');
    toast('已查询');
  });
  el.querySelector('#rExport').addEventListener('click', () => {
    api.download(`/api/reports/export?${filterQuery()}`);
    toast('报告已导出.xlsx');
  });
  // 行点击展开/收起详情（点 Allure 按钮除外）
  el.querySelectorAll('.rprow').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      const det = el.querySelector(`.rpdet[data-i="${row.dataset.i}"]`);
      det.style.display = det.style.display === 'none' ? 'table-row' : 'none';
    });
  });
  // 打开 Allure：列表行与详情内的按钮共用（首次点击后端惰性生成，约 5~15s）
  el.querySelectorAll('.alBtn').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      openAllure(b.dataset.id);
    });
  });
}

/** 打开报告的 Allure 页面。
 * 先同步开空白页再异步取地址 —— window.open 必须发生在用户手势内，
 * 否则等接口返回后再开会被浏览器弹窗拦截。 */
async function openAllure(reportId) {
  const win = window.open('', '_blank');
  if (win) win.document.write('<title>Allure</title><body style="font-family:sans-serif;color:#666;padding:40px;">正在生成 Allure 报告，首次约 5~15 秒，请稍候…</body>');
  try {
    const res = await api.get(`/api/reports/${reportId}/allure`);
    if (win) { win.location = res.url; } else { window.open(res.url, '_blank'); }
  } catch (err) {
    if (win) win.close();
    toast(err.message);
  }
}
