/* 执行中心：选任务 + 勾品牌 → 后端创建 job → 前端轮询点亮「用例 × 品牌」矩阵。
   矩阵/进度条/实时日志的节奏与原型演示一致（每格约 230ms）；执行完自动落库为报告。
   现场可恢复：job 状态全在后端，切走再回来 / 刷新页面都会自动重连进行中的执行；
   执行中可「终止」（已出结果保留，剩余记「未执行」灰格）。 */
import { api } from '../api.js';
import { root, phead, toast, opt, mdHead, openModal } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

let pollTimer = null;     // 轮询句柄：离开页面/重新渲染时清掉，避免泄漏
let currentJob = null;    // 当前 attach 的 job id（终止按钮用）
let lastProgress = null;  // 最近一帧进度快照（终止确认弹窗读设备数）

export async function render() {
  const brands = store.meta.device_brands;
  const devices = await api.get('/api/devices');
  const realDevs = devices.filter((d) => (d.udid || '').includes(':'));   // 真机台架（可点名）
  const realBrands = new Set(realDevs.map((d) => d.brand));

  // 设备卡片（借鉴 Codex 平台的按设备选择设计）：一台一列并行，富信息来自探活采集
  let firstChecked = false;
  const devCard = (d) => {
    const ok = d.online && d.agent_ready;
    const m = d.meta || {};
    const info = [m.android ? `Android ${m.android}` : (d.os || ''), m.api ? `API ${m.api}` : '',
      m.model ? `型号 ${m.model}` : '', d.resolution,
      m.locale ? `locale ${m.locale}` : '', m.app_version ? `App ${m.app_version}` : '']
      .filter(Boolean).join(' · ');
    const checked = ok && !firstChecked ? (firstChecked = true, ' checked') : '';
    return `<label style="display:block;flex:0 1 265px;min-width:235px;border:0.5px solid ${ok ? 'var(--color-border-info)' : 'var(--color-border-tertiary)'};border-radius:var(--border-radius-md);padding:8px 11px;cursor:${ok ? 'pointer' : 'not-allowed'};background:var(--color-background-tertiary);${ok ? '' : 'opacity:.6;'}">`
      + `<div style="display:flex;align-items:center;gap:7px;"><input type="checkbox" class="exdev" value="${d.id}"${checked}${ok ? '' : ' disabled'}><span style="font-weight:500;font-size:12.5px;color:var(--color-text-primary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${d.name}</span><span style="font-size:10.5px;color:${ok ? 'var(--color-text-success)' : 'var(--color-text-tertiary)'};">${ok ? '可执行' : (d.online ? '非root' : '离线')}</span></div>`
      + `<div style="font-family:var(--font-mono);font-size:11px;color:var(--color-text-info);margin:3px 0 1px 21px;">${d.udid}</div>`
      + `<div class="sub" style="font-size:10.5px;line-height:1.5;margin-left:21px;">${info || '—'}</div>`
      + '</label>';
  };
  // 无真机台架的品牌 → 模拟演示列（可选附加）
  const simChecks = brands.filter((b) => !realBrands.has(b)).map((b) =>
    `<label style="font-size:12px;color:var(--color-text-secondary);display:inline-flex;align-items:center;gap:4px;"><input type="checkbox" class="exsim" value="${b}"> ${b}<span class="sub" style="font-size:10px;">(模拟)</span></label>`).join(' ');
  const devBlock = '<div style="margin-bottom:13px;">'
    + '<div class="sub" style="margin-bottom:6px;">执行设备（可多选，一台一列并行；执行前自动环境预检）</div>'
    + `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:stretch;">${realDevs.map(devCard).join('')}`
    + (simChecks ? `<div style="display:flex;flex-direction:column;justify-content:center;gap:5px;padding:0 6px;">${simChecks}</div>` : '')
    + '</div></div>';

  const ctl = 'height:34px;font-size:13px;padding:0 10px;border-radius:var(--border-radius-md);';
  // 执行按钮 + 终止按钮（终止仅执行中显示；样式对齐 Codex 平台：红边「终止执行」）
  const runBtns = '<button id="runBtn" class="pbtn" style="margin-left:auto;"><i class="ti ti-player-play" style="vertical-align:-2px;" aria-hidden="true"></i> 开始执行</button>'
    + '<button id="stopBtn" class="gbtn" style="display:none;color:var(--color-text-danger);border-color:var(--color-text-danger);"><i class="ti ti-player-stop" style="vertical-align:-2px;" aria-hidden="true"></i> 终止执行</button>';

  // 脚本模式：从脚本管理「执行」进来，直接跑该脚本对应框架的用例（不受任务路由影响）
  if (store.execScript) {
    const s = store.execScript;
    return phead('执行中心 · 脚本', '直接执行指定脚本对应框架的用例')
      + `<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px;"><span style="display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 12px;border-radius:var(--border-radius-md);background:var(--color-background-info);color:var(--color-text-info);font-size:13px;"><i class="ti ti-file-code" aria-hidden="true"></i> ${s.name}</span><span class="lnk" id="exToTask" style="font-size:12px;">切回按任务执行</span>${runBtns}</div>`
      + devBlock + _panels();
  }

  // 任务模式（默认）
  const tasks = await api.get('/api/tasks');
  const names = tasks.map((t) => t.name);
  const selectedTask = store.execTask && names.includes(store.execTask) ? store.execTask : names[0];
  store.execTask = '';   // 预填只生效一次
  return phead('执行中心', '选择任务与执行设备，多台架并行执行')
    + `<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px;"><select id="exTask" style="${ctl}width:170px;">${names.map((n) => opt(n, selectedTask)).join('')}</select>${runBtns}</div>`
    + devBlock + _panels();
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
  currentJob = null;
  const el = root();
  el.querySelector('#runBtn').addEventListener('click', startRun);
  // 终止：平台风格确认弹窗（样式对齐 Codex 平台），确认后置停止标志 → 后端 kill pytest
  el.querySelector('#stopBtn').addEventListener('click', openStopConfirm);
  const toTask = el.querySelector('#exToTask');   // 脚本模式下「切回按任务执行」
  if (toTask) toTask.addEventListener('click', () => { store.execScript = null; go('exec'); });
  reconnect();   // 切走再回来 / 刷新页面：自动重连进行中的 job，恢复矩阵与日志
}

/** 终止确认弹窗：说明后果（已完成保留 / 其余记未执行）+ 涉及设备数，确认才下发 stop。 */
function openStopConfirm() {
  if (!currentJob) return;
  const jobId = currentJob;   // 弹窗打开期间 job 可能自然结束，快照当前 id
  const realDevs = lastProgress && lastProgress.targets
    ? lastProgress.targets.filter((t) => t.serial).length : 0;
  const html = mdHead('终止执行')
    + `<div style="font-size:12.5px;line-height:1.75;color:var(--color-text-secondary);margin:2px 0 16px;">将停止仍在预检或运行中的自动化任务。<span style="color:var(--color-text-primary);">已完成结果会保留</span>并照常落报告，其余用例标记为「未执行」。${realDevs ? `本次执行涉及 ${realDevs} 台设备。` : ''}</div>`
    + '<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">继续执行</button><button id="stopOk" class="pbtn" style="background:var(--color-text-danger);border-color:var(--color-text-danger);color:#fff;"><i class="ti ti-player-stop" style="vertical-align:-2px;" aria-hidden="true"></i> 确认终止</button></div>';
  const ov = openModal(html, 400);
  ov.querySelector('#stopOk').addEventListener('click', async (e) => {
    const b = e.target.closest('button');
    b.disabled = true;
    b.textContent = '终止中…';
    try { await api.post(`/api/run/${jobId}/stop`, {}); }
    catch (err) { toast(err.message); }
    ov.remove();
  });
}

/** 查询进行中的 job 并重连（现场数据全在后端，一次 progress 快照即可完整恢复）。 */
async function reconnect() {
  let act;
  try { act = await api.get('/api/run/active'); } catch (e) { return; }
  if (!act.length) return;
  if (act.length > 1) toast(`另有 ${act.length - 1} 个执行也在进行中（并行台架）`);
  attach(act[0].job, { fresh: false });
}

async function startRun() {
  const el = root();
  const runBtn = el.querySelector('#runBtn');
  const deviceIds = Array.from(el.querySelectorAll('.exdev:checked')).map((c) => +c.value);
  const brands = Array.from(el.querySelectorAll('.exsim:checked')).map((c) => c.value);
  if (!deviceIds.length && !brands.length) { toast('请至少选择一台执行设备（或模拟品牌）'); return; }

  runBtn.disabled = true;
  const body = { brands, device_ids: deviceIds };
  let job;
  try {
    // 脚本模式跑该脚本对应框架；任务模式跑任务（按覆盖最多的框架路由）
    job = store.execScript
      ? await api.post(`/api/scripts/${store.execScript.id}/run`, body)
      : await api.post('/api/run', { task: el.querySelector('#exTask').value, ...body });
  } catch (err) { toast(err.message); runBtn.disabled = false; return; }
  attach(job.job, { fresh: true });
}

/** 接管一个 job 的现场展示：画矩阵 → 200ms 轮询点亮 → 增量日志 →
    终态（done/stopped）恢复按钮。新发起与重连共用（数据源都是 progress 快照）。 */
function attach(jobId, { fresh }) {
  const el = root();
  const runBtn = el.querySelector('#runBtn');
  const stopBtn = el.querySelector('#stopBtn');
  currentJob = jobId;
  runBtn.disabled = true;
  stopBtn.style.display = '';
  stopBtn.disabled = false;
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }

  const log = el.querySelector('#exLog');
  log.innerHTML = fresh ? '' : '<div class="sub">› 已重连进行中的执行，恢复现场…</div>';
  log.style.color = 'var(--color-text-primary)';
  let renderedLogs = 0;   // 已渲染的日志条数（服务端日志数组只增不减，增量渲染）
  let drawn = false;      // 矩阵骨架只画一次（行/品牌来自首帧快照）

  async function tick() {
    let p;
    try {
      p = await api.get(`/api/run/${jobId}/progress`);
    } catch (err) {   // job 丢失（平台重启）等：收尾还原按钮
      clearInterval(pollTimer); pollTimer = null; currentJob = null;
      runBtn.disabled = false; stopBtn.style.display = 'none';
      toast(err.message); return;
    }
    lastProgress = p;   // 终止确认弹窗读设备数
    if (!drawn) { drawMatrix(p.rows, p.brands); drawn = true; }
    paintCells(p);
    el.querySelector('#exBar').style.width = `${Math.round((p.done / p.total) * 100)}%`;
    el.querySelector('#exProg').textContent = `执行中… ${p.done}/${p.total}`;
    for (; renderedLogs < p.logs.length; renderedLogs++) {
      const line = p.logs[renderedLogs];
      log.innerHTML += `<div${line.startsWith('✗') ? ' style="color:var(--color-text-danger);"' : ''}>${line}</div>`;
    }
    if (p.status === 'done' || p.status === 'stopped') {
      clearInterval(pollTimer); pollTimer = null; currentJob = null;
      el.querySelector('#exProg').textContent = p.summary;
      const d = document.createElement('div');
      d.style.marginTop = '6px';
      // 摘要首段着色：✓ 绿 / ⚠ 黄（终止），其余原样
      const [head, ...rest] = p.summary.split(' · ');
      const col = head.startsWith('✓') ? 'var(--color-text-success)' : 'var(--color-text-warning)';
      d.innerHTML = `<span style="color:${col};">${head}</span>${rest.length ? ' · ' + rest.join(' · ') : ''}`;
      log.appendChild(d);
      const el2 = root();   // 可能已切页，按当前 DOM 取
      const rb = el2.querySelector('#runBtn');
      const sb = el2.querySelector('#stopBtn');
      if (rb) rb.disabled = false;
      if (sb) sb.style.display = 'none';
    }
  }
  tick();                              // 立即拉一帧：重连时秒回现场
  pollTimer = setInterval(tick, 200);
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

/** 按 job.cells 状态点亮格子：run=黄 loader，ok=绿✓，fail=红✗，na=灰—（终止/超时未执行） */
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
    } else if (st === 'na') {
      cell.style.background = 'var(--color-background-secondary)';
      cell.style.color = 'var(--color-text-tertiary)';
      cell.innerHTML = '<span title="未执行（终止/超时截断）">—</span>';
    }
  }
}
