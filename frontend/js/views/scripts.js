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
    body += `<tr class="scrow hov" data-i="${i}" data-id="${s.id}" style="cursor:pointer;"><td style="font-weight:500;"><i class="ti ti-chevron-right scchev" data-i="${i}" style="vertical-align:-2px;color:var(--color-text-tertiary);transition:transform .15s;" aria-hidden="true"></i> ${s.name}</td><td class="sub">${s.app}</td><td>${s.cases.length} 条</td><td class="sub">${s.version}${s.versions.length > 1 ? ` <span style="font-size:10.5px;color:var(--color-text-tertiary);">(${s.versions.length}个版本)</span>` : ''}</td><td>${badge(rcls, rtxt)}</td><td style="text-align:right;white-space:nowrap;"><span class="lnk runbtn" data-id="${s.id}" data-name="${s.name}" title="在执行中心跑该脚本对应框架的用例" style="margin-right:12px;font-size:12.5px;">执行 ›</span><button class="iconbtn dlbtn" data-id="${s.id}" title="下载当前版本到本地" aria-label="下载脚本"><i class="ti ti-download" aria-hidden="true"></i></button></td></tr>`;

    // 展开行①：版本列表（多版本共存；覆盖率/执行以「当前」版本为准。仓库脚本无版本记录不显示）
    let verHtml = '';
    if (s.versions.length) {
      verHtml = `<div class="sub" style="margin-bottom:4px;">版本（${s.versions.length}）—— 覆盖率与执行以「当前」为准；重传同名同版本号可覆盖修复：</div>`
        + `<table class="tbl" style="margin-bottom:10px;"><thead><tr><th>版本</th><th>上传时间</th><th>映射用例</th><th>状态</th><th style="text-align:right;">操作</th></tr></thead><tbody>`
        + s.versions.map((v) => `<tr><td style="font-family:var(--font-mono);font-size:11.5px;">${v.version}</td><td class="sub">${v.created_at || '—'}</td><td>${v.case_count} 条</td><td>${v.active ? badge('b-ok', '当前') : ''}</td><td style="text-align:right;white-space:nowrap;">`
          + (!v.active ? `<span class="lnk vact" data-sid="${s.id}" data-vid="${v.id}" data-ver="${v.version}" style="font-size:12px;margin-right:12px;">设为当前</span>` : '')
          + (v.has_file ? `<span class="lnk vdl" data-sid="${s.id}" data-vid="${v.id}" style="font-size:12px;margin-right:12px;">下载</span>` : '')
          + (s.versions.length > 1 ? `<span class="lnk vdel" data-sid="${s.id}" data-vid="${v.id}" data-ver="${v.version}" style="font-size:12px;color:var(--color-text-danger);">删除</span>` : '')
          + '</td></tr>').join('')
        + '</tbody></table>';
    }
    // 展开行②：当前版本覆盖的手工用例明细
    const sub = `<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:8px 12px;">${verHtml}<div class="sub" style="margin-bottom:4px;">当前版本覆盖 ${s.cases.length} 条手工用例：</div><table class="tbl"><thead><tr><th>用例编号</th><th>功能模块</th><th>优先级</th></tr></thead><tbody>${s.cases.map((c) => `<tr><td style="font-family:var(--font-mono);font-size:11.5px;">${c.case_id}</td><td>${c.module}</td><td>${c.priority}</td></tr>`).join('')}</tbody></table></div>`;
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
  // 版本操作：设为当前 / 按版本下载 / 删除（展开区内，阻止冒泡防止行收起）
  el.querySelectorAll('.vact').forEach((b) => {
    b.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await api.post(`/api/scripts/${b.dataset.sid}/versions/${b.dataset.vid}/activate`, {});
        toast(`已切换到 ${b.dataset.ver} · 覆盖率与执行随之更新`);
        go('scripts');
      } catch (err) { toast(err.message); }
    });
  });
  el.querySelectorAll('.vdl').forEach((b) => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      api.download(`/api/scripts/${b.dataset.sid}/versions/${b.dataset.vid}/download`);
    });
  });
  el.querySelectorAll('.vdel').forEach((b) => {
    b.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!window.confirm(`确定删除版本 ${b.dataset.ver}？该版本的文件与映射快照将被移除。`)) return;
      try {
        await api.del(`/api/scripts/${b.dataset.sid}/versions/${b.dataset.vid}`);
        toast(`版本 ${b.dataset.ver} 已删除`);
        go('scripts');
      } catch (err) { toast(err.message); }
    });
  });
}

/* ---------------- 上传脚本弹窗（工作台快捷入口也会调用） ----------------
   映射全自动（标记/CSV/覆盖矩阵是唯一事实源，不再手工勾选）；
   多版本语义：同名+新版本号=新增版本并激活，同名+旧版本号=覆盖修复该版本。 */
export async function openUpload() {
  const scripts = await api.get('/api/scripts');   // 重名/版本冲突检测数据源
  const apps = store.meta.apps;

  const html = mdHead('上传自动化脚本')
    + '<div class="mdlab">脚本文件 (.py / .zip)</div>'
    + '<label style="display:flex;flex-direction:column;align-items:center;gap:5px;border:1px dashed var(--color-border-secondary);border-radius:var(--border-radius-md);padding:14px;cursor:pointer;color:var(--color-text-secondary);background:var(--color-background-tertiary);margin:5px 0 13px;"><i class="ti ti-cloud-upload" style="font-size:21px;" aria-hidden="true"></i><span id="mdFn" style="font-size:12px;">点击选择文件…</span><input id="mdFile" type="file" accept=".py,.zip" style="display:none;"></label>'
    + '<div class="mdlab">脚本名称</div><input id="mdName" type="text" placeholder="如 酷我音乐 · 播放回归" style="width:100%;margin:5px 0 13px;">'
    + `<div style="display:flex;gap:10px;"><div style="flex:1;min-width:0;"><div class="mdlab">关联 App</div><select id="mdApp" style="width:100%;margin:5px 0 13px;">${apps.map((a) => `<option>${a}</option>`).join('')}</select></div><div style="width:92px;"><div class="mdlab">版本</div><input id="mdVer" type="text" value="v1.0" style="width:100%;margin:5px 0 13px;"></div></div>`
    + '<div id="mdConflict" class="sub" style="display:none;margin:-6px 0 10px;font-size:11.5px;line-height:1.5;"></div>'
    + '<div class="mdlab" style="margin-bottom:5px;">映射识别（自动，无需勾选）</div>'
    + '<div id="mdSum" class="sub" style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:8px 11px;margin-bottom:15px;font-size:12px;line-height:1.6;">选择文件后自动识别框架与用例映射：Zcode/Media 包按包内映射表，其余按 <code>@pytest.mark.case</code> 标记。</div>'
    + `<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn"><i class="ti ti-upload" style="vertical-align:-2px;" aria-hidden="true"></i> 确定上传</button></div>`;
  const ov = openModal(html);
  let pickedFile = null;

  const FW_LABEL = { media_zcode: 'Zcode(u2) 包', media_automation: 'Media_automation 包', jdo: 'JDO 规范脚本' };

  // 选完文件 → 只读识别摘要（框架类型 + 映射命中统计 + 未命中编号明示）
  async function scanSummary(file) {
    const box = ov.querySelector('#mdSum');
    box.innerHTML = '识别中…';
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await api.postForm('/api/scripts/scan', fd);
      if (!r.framework) {
        box.innerHTML = '<span style="color:var(--color-text-warning);">未识别到框架特征或用例标记 —— 可以上传，但不会计入覆盖率。</span>请按 doc/脚本框架规范 打 <code>@pytest.mark.case</code> 标记。';
        return;
      }
      let h = `<span style="color:var(--color-text-info);">识别为 ${FW_LABEL[r.framework] || r.framework}</span> · 命中官方用例库 <b>${r.matched}</b> 条`
        + (r.unmatched ? ` · <span style="color:var(--color-text-warning);">${r.unmatched} 条未命中</span>` : '');
      if (r.unmatched_ids && r.unmatched_ids.length) {
        h += `<div style="margin-top:3px;color:var(--color-text-warning);">未命中编号（请改为官方 KW-000x 体系）：${r.unmatched_ids.slice(0, 8).join('、')}${r.unmatched_ids.length > 8 ? ' …' : ''}</div>`;
      }
      box.innerHTML = h;
    } catch (err) { box.innerHTML = `<span style="color:var(--color-text-danger);">${err.message}</span>`; }
  }

  // 名称/版本变化 → 重名与版本冲突提示（新版本号=新增版本，旧版本号=覆盖修复）
  function refreshConflict() {
    const tip = ov.querySelector('#mdConflict');
    const name = ov.querySelector('#mdName').value.trim();
    const ver = ov.querySelector('#mdVer').value.trim();
    const hit = scripts.find((s) => s.name === name && s.versions && s.versions.length);
    if (!hit) { tip.style.display = 'none'; return; }
    tip.style.display = '';
    const exists = hit.versions.find((v) => v.version === ver);
    tip.innerHTML = exists
      ? `<span style="color:var(--color-text-danger);">⚠ 已有脚本「${hit.name}」存在版本 ${ver} —— 上传将<b>覆盖</b>该版本的文件与映射${exists.active ? '（它是当前版本，覆盖率随之更新）' : ''}。</span>`
      : `<span style="color:var(--color-text-info);">已有脚本「${hit.name}」（${hit.versions.length} 个版本，当前 ${hit.version}）—— 将<b>新增版本 ${ver || '?'}</b> 并设为当前。</span>`;
  }
  ov.querySelector('#mdName').addEventListener('input', refreshConflict);
  ov.querySelector('#mdVer').addEventListener('input', refreshConflict);

  // 选文件后：大小校验 → 显示文件名 → 自动填脚本名 → 识别摘要
  ov.querySelector('#mdFile').addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    if (f.size > 50 * 1024 * 1024) { toast('文件超过 50MB 上限'); e.target.value = ''; return; }
    pickedFile = f;
    ov.querySelector('#mdFn').textContent = f.name;
    const nameInput = ov.querySelector('#mdName');
    if (!nameInput.value) nameInput.value = f.name.replace(/\.(py|zip)$/i, '').replace(/_/g, ' ');
    refreshConflict();
    scanSummary(f);
  });

  ov.querySelector('#mdOk').addEventListener('click', async () => {
    const name = ov.querySelector('#mdName').value.trim();
    if (!name) { toast('请填写脚本名称'); return; }
    if (!pickedFile) { toast('请选择脚本文件 (.py / .zip)'); return; }
    const fd = new FormData();
    fd.append('file', pickedFile);
    fd.append('name', name);
    fd.append('app', ov.querySelector('#mdApp').value);
    fd.append('version', ov.querySelector('#mdVer').value.trim() || 'v1.0');
    const okBtn = ov.querySelector('#mdOk');
    okBtn.disabled = true;
    try {
      const r = await api.postForm('/api/scripts/upload', fd);
      ov.remove();
      go('scripts');
      toast(r.message || `脚本「${name}」已上传`);
    } catch (err) { toast(err.message); okBtn.disabled = false; }
  });
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
  // 三套框架均可预览：jdo=平台脚手架（打包 framework/），zcode/media=最新上传的原包（直读 zip）
  const TABS = [['jdo', 'JDO 脚手架'], ['zcode', 'Zcode (u2)'], ['media', 'Media_automation']];
  // 内容区固定高度：三个 tab 内容量不同，高度锁死才不会来回撑缩导致弹窗抖动
  const html = mdHead('框架预览')
    + `<div style="display:flex;gap:6px;margin-bottom:10px;">${TABS.map(([k, l]) => `<button class="gbtn scfTab" data-fw="${k}" style="font-size:12px;height:28px;padding:0 12px;">${l}</button>`).join('')}</div>`
    + '<div id="scfWrap" style="height:412px;display:flex;flex-direction:column;"><div class="sub" style="padding:60px 0;text-align:center;">加载中…</div></div>'
    + '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:14px;"><button id="mdCancel" class="gbtn">关闭</button><button id="scfDl" class="pbtn" style="visibility:hidden;"></button></div>';
  const ov = openModal(html, 620);
  let dl = null;      // 当前 tab 的下载指向：jdo=脚手架 zip，其余=上传原包
  let loadSeq = 0;    // 连点 tab 时只认最后一次请求的结果

  ov.querySelectorAll('.scfTab').forEach((b) => b.addEventListener('click', () => loadFw(b.dataset.fw)));
  ov.querySelector('#scfDl').addEventListener('click', () => {
    if (dl) { api.download(dl.url); toast(`已开始下载 · ${dl.label}`); }
  });

  async function loadFw(fw) {
    ov.querySelectorAll('.scfTab').forEach((b) => {
      const on = b.dataset.fw === fw;
      b.style.background = on ? 'var(--color-background-info)' : '';
      b.style.color = on ? 'var(--color-text-info)' : '';
    });
    const wrap = ov.querySelector('#scfWrap');
    const dlBtn = ov.querySelector('#scfDl');
    const seq = ++loadSeq;
    let res;
    try {
      // 切换期间保留旧内容（本地接口很快），数据到了整体替换，避免「加载中」造成高度塌缩
      res = await api.get(`/api/scripts/scaffold/preview?fw=${fw}`);
    } catch (err) {   // 该框架尚无上传包（404）等：弹窗内提示，不打断
      if (seq !== loadSeq) return;
      wrap.innerHTML = `<div class="sub" style="padding:60px 0;text-align:center;">${err.message}</div>`;
      dlBtn.style.visibility = 'hidden'; dl = null; return;
    }
    if (seq !== loadSeq) return;
    dl = { url: res.download_url, label: res.download_label };
    dlBtn.style.visibility = '';
    dlBtn.innerHTML = `<i class="ti ti-download" style="vertical-align:-2px;" aria-hidden="true"></i> ${res.download_label}`;
    renderTree(wrap, res);
  }

  // ---- 目录树构建：目录带职责说明，文件缩进可点预览（三套框架通用，支持多顶层目录/根文件） ----
  function renderTree(wrap, res) {
    const files = res.files;
    const dirDescs = res.dirs || {};
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
    const fileRow = (i, depth) => {
      const f = files[i];
      return `<div class="scfItem" data-i="${i}" style="display:flex;justify-content:space-between;gap:8px;padding:3px 8px;margin-left:${depth * 12}px;border-radius:6px;cursor:pointer;font-size:12px;"><span style="font-family:var(--font-mono);color:var(--color-text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"><i class="ti ti-file-code" style="vertical-align:-2px;color:var(--color-text-tertiary);" aria-hidden="true"></i> ${f.path.split('/').pop()}</span><span class="sub" style="flex-shrink:0;">${fmtSize(f.size)}</span></div>`;
    };
    function walk(dir, depth) {
      const desc = dirDescs[dir] || '';
      listHtml += `<div style="padding:4px 6px 1px;margin-left:${depth * 12}px;">`
        + `<div style="font-size:12px;color:var(--color-text-primary);font-weight:500;"><i class="ti ti-folder" style="vertical-align:-2px;color:var(--color-text-warning);" aria-hidden="true"></i> ${dir.split('/').pop()}/</div>`
        + (desc ? `<div class="sub" style="font-size:10.5px;line-height:1.45;margin:1px 0 2px 17px;">${desc}</div>` : '')
        + '</div>';
      (childDirs[dir] || []).sort().forEach((d) => walk(d, depth + 1));
      (childFiles[dir] || []).forEach((i) => { listHtml += fileRow(i, depth + 1); });
    }
    (childDirs[''] || []).sort().forEach((d) => walk(d, 0));          // 顶层目录（jdo 只有 framework/）
    (childFiles[''] || []).forEach((i) => { listHtml += fileRow(i, 0); });  // zip 根下的散文件

    // 说明行固定预留两行高，树/预览用 flex 撑满剩余空间：各 tab 内容量不同但布局纹丝不动
    wrap.innerHTML = `<div class="sub" style="margin-bottom:8px;flex-shrink:0;min-height:34px;">${res.note ? `${res.note}。` : ''}${res.source ? `来源：脚本「${res.source}」上传包 · ` : ''}共 ${files.length} 个文件，点文件可预览内容。</div>`
      + '<div style="display:flex;gap:12px;flex:1;min-height:0;">'
      + `<div style="width:47%;flex-shrink:0;overflow:auto;border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:5px;">${listHtml}</div>`
      + '<div style="flex:1;min-width:0;display:flex;flex-direction:column;"><div id="scfName" class="sub" style="margin-bottom:5px;font-family:var(--font-mono);flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div><pre id="scfBody" style="margin:0;flex:1;overflow:auto;background:var(--color-background-tertiary);border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:10px 12px;font-family:var(--font-mono);font-size:11.5px;line-height:1.55;color:var(--color-text-primary);white-space:pre;"></pre></div>'
      + '</div>';

    function showFile(i) {
      const f = files[i];
      wrap.querySelector('#scfName').textContent = f.path;
      wrap.querySelector('#scfBody').innerHTML = f.content
        ? escapeHtml(f.content)
        : `<span style="color:var(--color-text-tertiary);">${f.text ? '（空文件）' : '（二进制或超大文件，不预览内容）'}</span>`;
      wrap.querySelectorAll('.scfItem').forEach((el) => {
        el.style.background = (+el.dataset.i === i) ? 'var(--color-background-info)' : '';
      });
    }
    wrap.querySelectorAll('.scfItem').forEach((el) => {
      el.addEventListener('click', () => showFile(+el.dataset.i));
    });
    // 默认展示：使用说明 / README / 覆盖矩阵，都没有则第一个文本文件
    const prefer = ['使用说明.md', 'readme.md', '覆盖矩阵'];
    let defIdx = -1;
    for (const key of prefer) {
      defIdx = files.findIndex((f) => f.path.toLowerCase().split('/').pop().includes(key.toLowerCase()));
      if (defIdx >= 0) break;
    }
    if (defIdx < 0) defIdx = Math.max(files.findIndex((f) => f.text), 0);
    showFile(defIdx);
  }

  loadFw('jdo');
}
