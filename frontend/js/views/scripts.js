/* 脚本管理（覆盖率分子）：上传（关联手工用例）/ 行展开映射明细 / 下载。
   交互与原型一致；上传走真实文件存储，下载可拉取原件到本地执行。 */
import { api } from '../api.js';
import { root, phead, btn, badge, toast, mdHead, openModal, flash } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

// 最近结果 -> 徽标（ok/fail/pending 与原型的 通过/失败/待执行 对应）
const RESULT_BADGE = { ok: ['b-ok', '通过'], fail: ['b-fail', '失败'], pending: ['b-mut', '待执行'] };

export async function render() {
  const scripts = await api.get('/api/scripts');
  const up = '<div id="scUp" style="border:1px dashed var(--color-border-secondary);border-radius:var(--border-radius-md);padding:16px;text-align:center;color:var(--color-text-secondary);margin-bottom:13px;background:var(--color-background-tertiary);cursor:pointer;"><i class="ti ti-cloud-upload" style="font-size:21px;" aria-hidden="true"></i><div style="font-size:12.5px;margin-top:4px;">点击上传 <code>.py</code> / <code>.zip</code>，并关联到测试用例</div></div>';

  let body = '';
  scripts.forEach((s, i) => {
    const [rcls, rtxt] = RESULT_BADGE[s.last_result] || RESULT_BADGE.pending;
    body += `<tr class="scrow hov" data-i="${i}" data-id="${s.id}" style="cursor:pointer;"><td style="font-weight:500;"><i class="ti ti-chevron-right scchev" data-i="${i}" style="vertical-align:-2px;color:var(--color-text-tertiary);transition:transform .15s;" aria-hidden="true"></i> ${s.name}</td><td class="sub">${s.app}</td><td>${s.cases.length} 条</td><td class="sub">${s.version}</td><td>${badge(rcls, rtxt)}</td><td style="text-align:right;white-space:nowrap;"><span class="lnk runbtn" data-id="${s.id}" data-name="${s.name}" title="在执行中心跑该脚本对应框架的用例" style="margin-right:12px;font-size:12.5px;">执行 ›</span><button class="iconbtn dlbtn" data-id="${s.id}" title="下载脚本到本地" aria-label="下载脚本"><i class="ti ti-download" aria-hidden="true"></i></button></td></tr>`;
    // 展开行：本脚本覆盖的手工用例明细
    const sub = `<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:8px 12px;"><div class="sub" style="margin-bottom:4px;">本脚本覆盖 ${s.cases.length} 条手工用例：</div><table class="tbl"><thead><tr><th>用例编号</th><th>功能模块</th><th>优先级</th></tr></thead><tbody>${s.cases.map((c) => `<tr><td style="font-family:var(--font-mono);font-size:11.5px;">${c.case_id}</td><td>${c.module}</td><td>${c.priority}</td></tr>`).join('')}</tbody></table></div>`;
    body += `<tr class="scdet" data-i="${i}" style="display:none;"><td colspan="6" style="padding:4px 7px 10px;">${sub}</td></tr>`;
  });

  return phead('脚本管理', '点开脚本行可查看其覆盖的手工用例；点下载按钮可拉取到本地执行',
    btn('框架脚手架', 'ti-package', 0, 'scScaffold') + ' ' + btn('上传脚本', 'ti-upload', 1, 'scUpBtn'))
    + up
    + `<table class="tbl"><thead><tr><th>脚本</th><th>关联 App</th><th>关联用例</th><th>版本</th><th>最近结果</th><th style="text-align:right;">操作</th></tr></thead><tbody>${body}</tbody></table>`;
}

export function init() {
  const el = root();
  el.querySelector('#scUpBtn').addEventListener('click', openUpload);
  el.querySelector('#scUp').addEventListener('click', openUpload);
  // 框架脚手架：先预览内容（文件树 + 点开看文件），确认后再下载
  el.querySelector('#scScaffold').addEventListener('click', openScaffoldPreview);
  // 行点击展开/收起映射明细（点下载/执行按钮除外），chevron 旋转 90°
  el.querySelectorAll('.scrow').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('.dlbtn') || e.target.closest('.runbtn')) return;
      const det = el.querySelector(`.scdet[data-i="${row.dataset.i}"]`);
      const chev = el.querySelector(`.scchev[data-i="${row.dataset.i}"]`);
      const open = det.style.display === 'none';
      det.style.display = open ? 'table-row' : 'none';
      chev.style.transform = open ? 'rotate(90deg)' : '';
    });
  });
  // 执行：进入执行中心「脚本模式」，跑该脚本对应框架的用例（点哪个跑哪个，不受任务路由）
  el.querySelectorAll('.runbtn').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      store.execScript = { id: +b.dataset.id, name: b.dataset.name };
      go('exec');
    });
  });
  // 下载：真实拉取原件 + 按钮 ✓ 闪烁反馈（与原型一致）
  el.querySelectorAll('.dlbtn').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      api.download(`/api/scripts/${b.dataset.id}/download`);
      flash(b);
    });
  });
}

/* ---------------- 上传脚本弹窗（工作台快捷入口也会调用） ---------------- */
export async function openUpload() {
  // 关联用例数据源：全部手工用例按 App 分组（原型的 casesByApp）
  const data = await api.get('/api/cases');
  const byApp = {};
  store.meta.apps.forEach((a) => { byApp[a] = []; });
  data.rows.forEach((c) => { (byApp[c.app] = byApp[c.app] || []).push(c); });
  const apps = Object.keys(byApp);

  const html = mdHead('上传自动化脚本')
    + '<div class="mdlab">脚本文件 (.py / .zip)</div>'
    + '<label style="display:flex;flex-direction:column;align-items:center;gap:5px;border:1px dashed var(--color-border-secondary);border-radius:var(--border-radius-md);padding:14px;cursor:pointer;color:var(--color-text-secondary);background:var(--color-background-tertiary);margin:5px 0 13px;"><i class="ti ti-cloud-upload" style="font-size:21px;" aria-hidden="true"></i><span id="mdFn" style="font-size:12px;">点击选择文件…</span><input id="mdFile" type="file" accept=".py,.zip" style="display:none;"></label>'
    + '<div class="mdlab">脚本名称</div><input id="mdName" type="text" placeholder="如 酷我音乐 · 播放回归" style="width:100%;margin:5px 0 13px;">'
    + `<div style="display:flex;gap:10px;"><div style="flex:1;min-width:0;"><div class="mdlab">关联 App</div><select id="mdApp" style="width:100%;margin:5px 0 13px;">${apps.map((a) => `<option>${a}</option>`).join('')}</select></div><div style="width:92px;"><div class="mdlab">版本</div><input id="mdVer" type="text" value="v1.0" style="width:100%;margin:5px 0 13px;"></div></div>`
    + '<div class="mdlab" style="margin-bottom:5px;">关联手工用例 <span id="mdCnt" style="color:var(--color-text-info);"></span></div>'
    + '<div style="display:flex;gap:8px;margin-bottom:6px;"><span id="mdAll" class="lnk" style="font-size:11px;">全选</span><span id="mdNone" class="lnk" style="font-size:11px;">清空</span></div>'
    + '<div id="mdCases" style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:8px 11px;margin-bottom:15px;"></div>'
    + `<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn"><i class="ti ti-upload" style="vertical-align:-2px;" aria-hidden="true"></i> 确定上传</button></div>`;
  const ov = openModal(html);
  let pickedFile = null;
  let scannedIds = [];   // 从脚本文件里扫出的 @pytest.mark.case 编号（自动勾选依据）

  // 切换 App 时重画该 App 的用例勾选列表（已扫描到的编号保持自动勾选）
  function renderCases() {
    const app = ov.querySelector('#mdApp').value;
    const list = byApp[app] || [];
    ov.querySelector('#mdCases').innerHTML = list.length
      ? list.map((c) => `<label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--color-text-primary);padding:3px 0;"><input type="checkbox" class="mdc" value="${c.id}" data-m="${c.module}" data-p="${c.priority}"${scannedIds.includes(c.id) ? ' checked' : ''}> <span style="font-family:var(--font-mono);font-size:11px;">${c.id}</span> <span class="sub">${c.module} · ${c.priority}</span></label>`).join('')
      : '<div class="sub" style="padding:4px 0;">该 App 暂无手工用例，请先到「测试用例」录入</div>';
    ov.querySelectorAll('.mdc').forEach((c) => c.addEventListener('change', updateCount));
    updateCount();
  }

  // 扫描文件内的用例标记并自动勾选（标记即映射表，无需手工比对）
  async function scanAndCheck(file) {
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.postForm('/api/scripts/scan', fd);
      scannedIds = res.cases;
      if (!scannedIds.length) { toast('文件中未识别到 @pytest.mark.case 标记，请手动勾选'); return; }
      let matched = 0;
      ov.querySelectorAll('.mdc').forEach((c) => {
        if (scannedIds.includes(c.value)) { c.checked = true; matched++; }
      });
      updateCount();
      const unmatched = scannedIds.length - matched;
      toast(`已识别 ${scannedIds.length} 条用例标记，自动勾选 ${matched} 条`
        + (unmatched ? `（${unmatched} 条不在当前 App 用例库）` : ''));
    } catch (err) { toast(err.message); }
  }
  function updateCount() {
    const n = ov.querySelectorAll('.mdc:checked').length;
    ov.querySelector('#mdCnt').textContent = n ? `已选 ${n} 条` : '';
  }

  ov.querySelector('#mdApp').addEventListener('change', renderCases);
  ov.querySelector('#mdAll').addEventListener('click', () => { ov.querySelectorAll('.mdc').forEach((c) => { c.checked = true; }); updateCount(); });
  ov.querySelector('#mdNone').addEventListener('click', () => { ov.querySelectorAll('.mdc').forEach((c) => { c.checked = false; }); updateCount(); });

  // 选文件后：大小校验 → 显示文件名 → 自动填脚本名 → 扫描标记自动勾选
  ov.querySelector('#mdFile').addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    if (f.size > 50 * 1024 * 1024) { toast('文件超过 50MB 上限'); e.target.value = ''; return; }
    pickedFile = f;
    ov.querySelector('#mdFn').textContent = f.name;
    const nameInput = ov.querySelector('#mdName');
    if (!nameInput.value) nameInput.value = f.name.replace(/\.(py|zip)$/i, '').replace(/_/g, ' ');
    scanAndCheck(f);
  });

  ov.querySelector('#mdOk').addEventListener('click', async () => {
    const name = ov.querySelector('#mdName').value.trim();
    const app = ov.querySelector('#mdApp').value;
    const ver = ov.querySelector('#mdVer').value.trim() || 'v1.0';
    const picked = Array.from(ov.querySelectorAll('.mdc:checked')).map((c) => [c.value, c.dataset.m, c.dataset.p]);
    if (!name) { toast('请填写脚本名称'); return; }
    if (!picked.length) { toast('请至少关联 1 条手工用例'); return; }
    if (!pickedFile) { toast('请选择脚本文件 (.py / .zip)'); return; }   // 真实上传必须有文件
    const fd = new FormData();
    fd.append('file', pickedFile);
    fd.append('name', name);
    fd.append('app', app);
    fd.append('version', ver);
    fd.append('cases', JSON.stringify(picked));
    try {
      await api.postForm('/api/scripts/upload', fd);
      ov.remove();
      go('scripts');
      toast(`脚本「${name}」已上传 · 关联 ${picked.length} 条用例`);
    } catch (err) { toast(err.message); }
  });

  renderCases();
}

/* ---------------- 框架脚手架预览弹窗（先看内容，再决定下载） ---------------- */
function fmtSize(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

async function openScaffoldPreview() {
  let files; let dirDescs;
  try {
    const res = await api.get('/api/scripts/scaffold/preview');
    files = res.files;
    dirDescs = res.dirs || {};
  } catch (err) { toast(err.message); return; }

  // ---- 目录树构建：目录带职责说明，文件缩进可点预览 ----
  const childDirs = {};   // 父目录 -> 子目录列表
  const childFiles = {};  // 目录 -> 文件下标列表
  const allDirs = new Set();
  files.forEach((f, i) => {
    const parts = f.path.split('/');
    for (let d = 1; d < parts.length; d++) allDirs.add(parts.slice(0, d).join('/'));
    const dir = parts.slice(0, -1).join('/');
    (childFiles[dir] = childFiles[dir] || []).push(i);
  });
  allDirs.forEach((d) => {
    const parent = d.includes('/') ? d.split('/').slice(0, -1).join('/') : '';
    (childDirs[parent] = childDirs[parent] || []).push(d);
  });

  let listHtml = '';
  function walk(dir, depth) {
    const desc = dirDescs[dir] || '';
    listHtml += `<div style="padding:4px 6px 1px;margin-left:${depth * 12}px;">`
      + `<div style="font-size:12px;color:var(--color-text-primary);font-weight:500;"><i class="ti ti-folder" style="vertical-align:-2px;color:var(--color-text-warning);" aria-hidden="true"></i> ${dir.split('/').pop()}/</div>`
      + (desc ? `<div class="sub" style="font-size:10.5px;line-height:1.45;margin:1px 0 2px 17px;">${desc}</div>` : '')
      + '</div>';
    (childDirs[dir] || []).sort().forEach((d) => walk(d, depth + 1));
    (childFiles[dir] || []).forEach((i) => {
      const f = files[i];
      listHtml += `<div class="scfItem" data-i="${i}" style="display:flex;justify-content:space-between;gap:8px;padding:3px 8px;margin-left:${(depth + 1) * 12}px;border-radius:6px;cursor:pointer;font-size:12px;"><span style="font-family:var(--font-mono);color:var(--color-text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"><i class="ti ti-file-code" style="vertical-align:-2px;color:var(--color-text-tertiary);" aria-hidden="true"></i> ${f.path.split('/').pop()}</span><span class="sub" style="flex-shrink:0;">${fmtSize(f.size)}</span></div>`;
    });
  }
  walk('framework', 0);

  const html = mdHead('框架脚手架 · 预览')
    + `<div class="sub" style="margin-bottom:10px;">同事下载后配合此包即可本地执行脚本（解压 → 装依赖 → 放脚本进 testcases → pytest）。共 ${files.length} 个文件，点文件可预览内容。</div>`
    + '<div style="display:flex;gap:12px;">'
    + `<div style="width:47%;flex-shrink:0;max-height:340px;overflow:auto;border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:5px;">${listHtml}</div>`
    + '<div style="flex:1;min-width:0;"><div id="scfName" class="sub" style="margin-bottom:5px;font-family:var(--font-mono);"></div><pre id="scfBody" style="margin:0;max-height:312px;overflow:auto;background:var(--color-background-tertiary);border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:10px 12px;font-family:var(--font-mono);font-size:11.5px;line-height:1.55;color:var(--color-text-primary);white-space:pre;"></pre></div>'
    + '</div>'
    + `<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:14px;"><button id="mdCancel" class="gbtn">关闭</button><button id="scfDl" class="pbtn"><i class="ti ti-download" style="vertical-align:-2px;" aria-hidden="true"></i> 下载脚手架 zip</button></div>`;
  const ov = openModal(html, 620);

  function showFile(i) {
    const f = files[i];
    ov.querySelector('#scfName').textContent = f.path;
    ov.querySelector('#scfBody').innerHTML = f.content
      ? escapeHtml(f.content)
      : `<span style="color:var(--color-text-tertiary);">${f.text ? '（空文件）' : '（二进制或超大文件，不预览内容）'}</span>`;
    ov.querySelectorAll('.scfItem').forEach((el) => {
      el.style.background = (+el.dataset.i === i) ? 'var(--color-background-info)' : '';
    });
  }
  ov.querySelectorAll('.scfItem').forEach((el) => {
    el.addEventListener('click', () => showFile(+el.dataset.i));
  });
  // 默认展示使用说明.md（找不到则第一个）
  const defIdx = files.findIndex((f) => f.path.endsWith('使用说明.md'));
  showFile(defIdx >= 0 ? defIdx : 0);

  ov.querySelector('#scfDl').addEventListener('click', () => {
    api.download('/api/scripts/scaffold');
    toast('框架脚手架.zip 已下载 · 解压后按使用说明操作');
  });
}
