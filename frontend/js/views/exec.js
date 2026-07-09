/* 执行中心：选任务 + 勾品牌 → 后端创建 job → 前端轮询点亮「用例 × 品牌」矩阵。
   矩阵/进度条/实时日志的节奏与原型演示一致（每格约 230ms）；执行完自动落库为报告。 */
import { api } from '../api.js';
import { root, phead, toast, opt } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

let pollTimer = null;   // 轮询句柄：离开页面/重新渲染时清掉，避免泄漏

export async function render() {
  const brands = store.meta.device_brands;
  // 默认前两个品牌勾选（与原型一致：奥迪/保时捷勾选、大众不勾）
  const brandChecks = brands.map((b, i) => `<label style="font-size:13px;color:var(--color-text-primary);display:inline-flex;align-items:center;gap:4px;"><input type="checkbox" class="exb" value="${b}"${i < 2 ? ' checked' : ''}> ${b}</label>`).join('');
  const ctl = 'height:34px;font-size:13px;padding:0 10px;border-radius:var(--border-radius-md);';

  // 脚本模式：从脚本管理「执行」进来，直接跑该脚本对应框架的用例（不受任务路由影响）
  if (store.execScript) {
    const s = store.execScript;
    return phead('执行中心 · 脚本', '直接执行指定脚本对应框架的用例')
      + `<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px;"><span style="display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 12px;border-radius:var(--border-radius-md);background:var(--color-background-info);color:var(--color-text-info);font-size:13px;"><i class="ti ti-file-code" aria-hidden="true"></i> ${s.name}</span><span class="lnk" id="exToTask" style="font-size:12px;">切回按任务执行</span><span class="sub">品牌</span>${brandChecks}<button id="runBtn" class="pbtn" style="margin-left:auto;"><i class="ti ti-player-play" style="vertical-align:-2px;" aria-hidden="true"></i> 开始执行</button></div>`
      + _panels();
  }

  // 任务模式（默认）
  const tasks = await api.get('/api/tasks');
  const names = tasks.map((t) => t.name);
  const selectedTask = store.execTask && names.includes(store.execTask) ? store.execTask : names[0];
  store.execTask = '';   // 预填只生效一次
  return phead('执行中心', '选择任务并勾选品牌，一键多品牌并行执行')
    + `<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px;"><select id="exTask" style="${ctl}width:170px;">${names.map((n) => opt(n, selectedTask)).join('')}</select><span class="sub">品牌</span>${brandChecks}<button id="runBtn" class="pbtn" style="margin-left:auto;"><i class="ti ti-player-play" style="vertical-align:-2px;" aria-hidden="true"></i> 开始执行</button></div>`
    + _panels();
}

/** 进度条 + 实时矩阵 + 实时日志（任务/脚本两模式共用的下半部分）。 */
function _panels() {
  return '<div style="height:6px;background:var(--color-background-secondary);border-radius:3px;overflow:hidden;margin-bottom:5px;"><div id="exBar" style="height:100%;width:0;background:var(--color-text-success);transition:width .2s;"></div></div>'
    + '<div class="sub" id="exProg" style="margin-bottom:12px;">就绪 · 勾选品牌后点「开始执行」</div>'
    + '<div id="exMatrix" style="margin-bottom:13px;"></div>'
    + '<div class="sub" style="margin-bottom:4px;">实时日志</div>'
    + '<div id="exLog" style="font-family:var(--font-mono);font-size:11.5px;line-height:1.7;background:var(--color-background-tertiary);border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:10px 12px;min-height:84px;color:var(--color-text-secondary);">等待执行…</div>';
}

export function init() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  const el = root();
  el.querySelector('#runBtn').addEventListener('click', startRun);
  const toTask = el.querySelector('#exToTask');   // 脚本模式下「切回按任务执行」
  if (toTask) toTask.addEventListener('click', () => { store.execScript = null; go('exec'); });
}

async function startRun() {
  const el = root();
  const runBtn = el.querySelector('#runBtn');
  const brands = Array.from(el.querySelectorAll('.exb:checked')).map((c) => c.value);
  if (!brands.length) { toast('请至少勾选一个品牌'); return; }

  runBtn.disabled = true;
  const log = el.querySelector('#exLog');
  log.innerHTML = '';
  log.style.color = 'var(--color-text-primary)';

  let job;
  try {
    // 脚本模式跑该脚本对应框架；任务模式跑任务（按覆盖最多的框架路由）
    job = store.execScript
      ? await api.post(`/api/scripts/${store.execScript.id}/run`, { brands })
      : await api.post('/api/run', { task: el.querySelector('#exTask').value, brands });
  } catch (err) { toast(err.message); runBtn.disabled = false; return; }

  drawMatrix(job.rows, job.brands);
  el.querySelector('#exProg').textContent = `执行中… 0/${job.total}`;

  let renderedLogs = 0;   // 已渲染的日志条数（服务端日志数组只增不减，增量渲染）
  pollTimer = setInterval(async () => {
    let p;
    try {
      p = await api.get(`/api/run/${job.job}/progress`);
    } catch (err) { clearInterval(pollTimer); pollTimer = null; runBtn.disabled = false; toast(err.message); return; }

    paintCells(p);
    el.querySelector('#exBar').style.width = `${Math.round((p.done / p.total) * 100)}%`;
    el.querySelector('#exProg').textContent = `执行中… ${p.done}/${p.total}`;
    // 增量追加日志（连接设备/失败明细）
    for (; renderedLogs < p.logs.length; renderedLogs++) {
      const line = p.logs[renderedLogs];
      log.innerHTML += `<div${line.startsWith('✗') ? ' style="color:var(--color-text-danger);"' : ''}>${line}</div>`;
    }
    if (p.status === 'done') {
      clearInterval(pollTimer); pollTimer = null;
      const d = document.createElement('div');
      d.style.marginTop = '6px';
      // 摘要 '✓ 执行完成 · 通过 N/M · 失败 K'，✓ 部分绿色（与原型一致）
      const [okPart, ...rest] = p.summary.split(' · ');
      d.innerHTML = `<span style="color:var(--color-text-success);">${okPart}</span> · ${rest.join(' · ')}`;
      log.appendChild(d);
      const runBtn2 = root().querySelector('#runBtn');
      if (runBtn2) runBtn2.disabled = false;
    }
  }, 200);
}

/** 画矩阵骨架：行 = 用例，列 = 品牌，格子初始为 「·」 */
function drawMatrix(rows, brands) {
  let g = `<div style="display:grid;grid-template-columns:90px repeat(${brands.length},1fr);gap:4px;font-size:11.5px;"><div></div>`
    + brands.map((b) => `<div style="text-align:center;color:var(--color-text-secondary);">${b}</div>`).join('');
  rows.forEach((label, ci) => {
    g += `<div style="display:flex;align-items:center;color:var(--color-text-secondary);">${label}</div>`;
    brands.forEach((b, bi) => {
      g += `<div id="cell-${ci}-${bi}" style="text-align:center;padding:6px 0;border-radius:4px;background:var(--color-background-secondary);color:var(--color-text-tertiary);">·</div>`;
    });
  });
  g += '</div>';
  root().querySelector('#exMatrix').innerHTML = g;
}

/** 按 job.cells 状态点亮格子：run=黄色 loader，ok=绿✓，fail=红✗ */
function paintCells(p) {
  const el = root();
  for (const key in p.cells) {
    const cell = el.querySelector(`#cell-${key}`);
    if (!cell) continue;
    const st = p.cells[key];
    if (st === 'run') {
      cell.style.background = 'var(--color-background-warning)';
      cell.style.color = 'var(--color-text-warning)';
      cell.innerHTML = '<i class="ti ti-loader" aria-hidden="true"></i>';
    } else if (st === 'ok') {
      cell.style.background = 'var(--color-background-success)';
      cell.style.color = 'var(--color-text-success)';
      cell.innerHTML = '<i class="ti ti-check" aria-hidden="true"></i>';
    } else if (st === 'fail') {
      cell.style.background = 'var(--color-background-danger)';
      cell.style.color = 'var(--color-text-danger)';
      cell.innerHTML = '<i class="ti ti-x" aria-hidden="true"></i>';
    }
  }
}
