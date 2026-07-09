/* 测试用例（覆盖率分母）：筛选 / Excel 导入(预览+upsert) / 导出 / 新增。
   交互与原型一致；数据全部走后端，自动化状态由脚本映射自动判定。 */
import { api } from '../api.js';
import { root, phead, btn, badge, opt, toast, mdHead, openModal } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

/** 当前筛选转 query string（导出复用同一份筛选） */
function filterQuery() {
  const f = store.caseFilter;
  return `app=${encodeURIComponent(f.app)}&priority=${encodeURIComponent(f.prio)}&status=${encodeURIComponent(f.status)}`;
}

export async function render() {
  const f = store.caseFilter;
  const data = await api.get(`/api/cases?${filterQuery()}`);
  const rows = data.rows;

  const appOpts = opt('全部 App', f.app) + store.meta.apps.map((a) => opt(a, f.app)).join('');
  const priOpts = ['全部优先级', 'P1', 'P2', 'P3', 'P4'].map((v) => opt(v, f.prio)).join('');
  const stOpts = ['全部状态', '已自动化', '待自动化'].map((v) => opt(v, f.status)).join('');

  // 筛选下拉统一样式：加大高度/宽度/字号，与工具栏按钮视觉协调
  const selStyle = 'height:34px;font-size:13px;padding:0 10px;border-radius:var(--border-radius-md);';
  const toolbar = '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;">'
    + `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;"><select id="fApp" style="${selStyle}width:140px;">${appOpts}</select><select id="fPrio" style="${selStyle}width:120px;">${priOpts}</select><select id="fStatus" style="${selStyle}width:130px;">${stOpts}</select></div>`
    + `<div style="display:flex;gap:8px;">${btn('导入官方用例', 'ti-file-database', 0, 'cImportOfficial')}${btn('导入 Excel', 'ti-file-import', 0, 'cImport')}${btn('导出 Excel', 'ti-file-export', 0, 'cExport')}${btn('新增用例', 'ti-plus', 1, 'cAdd')}</div></div>`;

  const body = rows.length
    ? rows.map((c) => `<tr class="hov"><td style="font-family:var(--font-mono);font-size:11.5px;">${c.id}</td><td>${c.app}</td><td>${c.title ? `<span title="${c.title}">${c.title}</span>` : '<span class="sub">—</span>'}</td><td>${c.module}</td><td>${c.priority}</td><td>${c.script ? badge('b-ok', '已自动化') : badge('b-mut', '待自动化')}</td><td>${c.script ? `<span class="lnk">${c.script}</span>` : '<span class="sub">—</span>'}</td></tr>`).join('')
    : '<tr><td colspan="7" class="sub" style="text-align:center;padding:18px;">无匹配用例</td></tr>';

  return phead('测试用例库', '手工回归 checklist —— 覆盖率的分母，「关联脚本」列体现每条用例由哪个脚本自动化',
    `<span class="sub">共 ${data.total} 条 · 筛出 ${rows.length} 条</span>`)
    + toolbar
    + `<table class="tbl"><thead><tr><th>用例编号</th><th>所属 App</th><th>用例标题</th><th>功能模块</th><th>优先级</th><th>自动化状态</th><th>关联脚本</th></tr></thead><tbody>${body}</tbody></table>`;
}

export function init() {
  const el = root();
  // 筛选联动：change 即刷新（与原型一致）
  [['#fApp', 'app'], ['#fPrio', 'prio'], ['#fStatus', 'status']].forEach(([sel, key]) => {
    el.querySelector(sel).addEventListener('change', (e) => {
      store.caseFilter[key] = e.target.value;
      go('cases');
    });
  });
  el.querySelector('#cImportOfficial').addEventListener('click', openImportOfficial);
  el.querySelector('#cImport').addEventListener('click', openImport);
  el.querySelector('#cExport').addEventListener('click', async () => {
    const data = await api.get(`/api/cases?${filterQuery()}`);
    api.download(`/api/cases/export?${filterQuery()}`);
    toast(`已导出当前用例清单.xlsx（${data.rows.length} 条）`);
  });
  el.querySelector('#cAdd').addEventListener('click', openAddCase);
}

/* ---------------- 导入 Excel 弹窗 ---------------- */
export function openImport() {
  const html = mdHead('导入功能用例（Excel）')
    + '<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:10px 12px;font-size:11.5px;color:var(--color-text-secondary);line-height:1.7;margin-bottom:12px;">支持 <code>.xlsx</code>，模板列：用例编号 / 所属App / 功能模块 / 优先级。<br>以「用例编号」为主键：已存在则更新、不存在则新增。<br>自动化状态由关联脚本自动判定，无需导入。</div>'
    + '<div style="margin-bottom:12px;"><span id="mdTpl" class="lnk" style="font-size:12px;"><i class="ti ti-download" style="vertical-align:-2px;" aria-hidden="true"></i> 下载导入模板.xlsx</span></div>'
    + '<div class="mdlab">Excel 文件</div>'
    + '<label style="display:flex;flex-direction:column;align-items:center;gap:5px;border:1px dashed var(--color-border-secondary);border-radius:var(--border-radius-md);padding:14px;cursor:pointer;color:var(--color-text-secondary);background:var(--color-background-tertiary);margin:5px 0 12px;"><i class="ti ti-file-spreadsheet" style="font-size:21px;" aria-hidden="true"></i><span id="mdFn" style="font-size:12px;">点击选择 .xlsx 文件…</span><input id="mdFile" type="file" accept=".xlsx,.xls" style="display:none;"></label>'
    + '<div id="mdParse" style="display:none;background:var(--color-background-secondary);border-radius:var(--border-radius-md);padding:9px 12px;font-size:12px;color:var(--color-text-primary);margin-bottom:13px;"></div>'
    + `<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn"><i class="ti ti-file-import" style="vertical-align:-2px;" aria-hidden="true"></i> 确定导入</button></div>`;
  const ov = openModal(html);
  let pickedFile = null;   // 预览通过的文件，点「确定导入」时真正提交
  let parsedCount = 0;

  ov.querySelector('#mdTpl').addEventListener('click', () => {
    api.download('/api/cases/template');
    toast('导入模板已下载');
  });

  // 选完文件先 dry_run 解析预览（与原型「已解析 N 条 · 新增 X / 更新 Y」一致）
  ov.querySelector('#mdFile').addEventListener('change', async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    ov.querySelector('#mdFn').textContent = f.name;
    const p = ov.querySelector('#mdParse');
    const fd = new FormData();
    fd.append('file', f);
    try {
      const r = await api.postForm('/api/cases/import?dry_run=1', fd);
      pickedFile = f;
      parsedCount = r.parsed;
      const errText = r.errors.length ? `${r.errors.length} 行错误` : '无错误行';
      p.style.display = 'block';
      p.innerHTML = `<i class="ti ti-circle-check" style="color:var(--color-text-success);vertical-align:-2px;" aria-hidden="true"></i> 已解析 ${r.parsed} 条 · 新增 ${r.added} / 更新 ${r.updated} · ${errText}`;
    } catch (err) {
      pickedFile = null;
      p.style.display = 'block';
      p.innerHTML = `<i class="ti ti-alert-circle" style="color:var(--color-text-danger);vertical-align:-2px;" aria-hidden="true"></i> ${err.message}`;
    }
  });

  ov.querySelector('#mdOk').addEventListener('click', async () => {
    if (!pickedFile) { toast('请先选择 Excel 文件'); return; }
    const fd = new FormData();
    fd.append('file', pickedFile);
    try {
      await api.postForm('/api/cases/import?dry_run=0', fd);
      ov.remove();
      go('cases');
      toast(`成功导入 ${parsedCount} 条功能用例`);
    } catch (err) { toast(err.message); }
  });
}

/* ---------------- 导入官方用例库弹窗 ---------------- */
export function openImportOfficial() {
  const html = mdHead('导入官方用例库（测试报告 Excel）')
    + '<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:10px 12px;font-size:11.5px;color:var(--color-text-secondary);line-height:1.7;margin-bottom:12px;">导入官方《One Info MEDIA 测试报告》.xlsx，按 sheet 识别各 App（酷我/喜马拉雅/乐听/爱奇艺），逐条落入手工用例库（覆盖率分母）。<br><b style="color:var(--color-text-warning);">整库替换</b>：将清空现有用例与映射，用官方用例替换种子数据。</div>'
    + '<div class="mdlab">Excel 文件 (.xlsx)</div>'
    + '<label style="display:flex;flex-direction:column;align-items:center;gap:5px;border:1px dashed var(--color-border-secondary);border-radius:var(--border-radius-md);padding:14px;cursor:pointer;color:var(--color-text-secondary);background:var(--color-background-tertiary);margin:5px 0 12px;"><i class="ti ti-file-database" style="font-size:21px;" aria-hidden="true"></i><span id="mdFn" style="font-size:12px;">点击选择官方测试报告 .xlsx…</span><input id="mdFile" type="file" accept=".xlsx" style="display:none;"></label>'
    + '<div id="mdBusy" style="display:none;font-size:12px;color:var(--color-text-secondary);margin-bottom:12px;">正在解析导入…</div>'
    + `<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn"><i class="ti ti-database-import" style="vertical-align:-2px;" aria-hidden="true"></i> 确定导入</button></div>`;
  const ov = openModal(html);
  let pickedFile = null;
  ov.querySelector('#mdFile').addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    if (f) { pickedFile = f; ov.querySelector('#mdFn').textContent = f.name; }
  });
  ov.querySelector('#mdOk').addEventListener('click', async () => {
    if (!pickedFile) { toast('请先选择官方测试报告 .xlsx'); return; }
    ov.querySelector('#mdBusy').style.display = 'block';
    const fd = new FormData();
    fd.append('file', pickedFile);
    try {
      const r = await api.postForm('/api/cases/import-official?replace=1', fd);
      const detail = Object.entries(r.apps).map(([a, n]) => `${a} ${n}`).join(' · ');
      ov.remove();
      go('cases');
      toast(`已导入官方用例 ${r.total} 条（${detail}）`);
    } catch (err) {
      ov.querySelector('#mdBusy').style.display = 'none';
      toast(err.message);
    }
  });
}

/* ---------------- 新增功能用例弹窗 ---------------- */
export function openAddCase() {
  const apps = store.meta.apps;
  const html = mdHead('新增功能用例')
    + '<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:9px 12px;font-size:11.5px;color:var(--color-text-secondary);line-height:1.6;margin-bottom:13px;">功能（手工）用例 —— 描述"测什么"。自动化状态由关联脚本自动判定，无需在此填写。</div>'
    + '<div style="display:flex;gap:10px;"><div style="flex:1;min-width:0;"><div class="mdlab">用例编号</div><input id="acId" type="text" placeholder="如 KW-PLAY-010" style="width:100%;margin:5px 0 12px;"></div><div style="width:96px;"><div class="mdlab">优先级</div><select id="acPri" style="width:100%;margin:5px 0 12px;"><option>P0</option><option>P1</option></select></div></div>'
    + `<div class="mdlab">所属 App</div><select id="acApp" style="width:100%;margin:5px 0 12px;">${apps.map((a) => `<option>${a}</option>`).join('')}</select>`
    + '<div class="mdlab">功能模块</div><input id="acMod" type="text" placeholder="如 播放控制" style="width:100%;margin:5px 0 15px;">'
    + '<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn">确定新增</button></div>';
  const ov = openModal(html);

  ov.querySelector('#mdOk').addEventListener('click', async () => {
    const id = ov.querySelector('#acId').value.trim();
    const app = ov.querySelector('#acApp').value;
    const mod = ov.querySelector('#acMod').value.trim();
    const pri = ov.querySelector('#acPri').value;
    if (!id) { toast('请填写用例编号'); return; }
    if (!mod) { toast('请填写功能模块'); return; }
    try {
      await api.post('/api/cases', { id, app, module: mod, priority: pri });
      ov.remove();
      go('cases');
      toast(`已新增功能用例 ${id}`);
    } catch (err) { toast(err.message); }   // 「用例编号已存在」等
  });
}
