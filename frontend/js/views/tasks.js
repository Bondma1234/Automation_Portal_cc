/* 测试任务：把用例组合成回归套件；新建弹窗实时预估用例数；「执行 ›」跳转执行中心并预填任务。 */
import { api } from '../api.js';
import { root, phead, btn, toast, mdHead, openModal } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

export async function render() {
  const tasks = await api.get('/api/tasks');
  const body = tasks.map((t) => `<tr class="hov"><td style="font-weight:500;">${t.name}</td><td class="sub">${t.apps_label}</td><td class="sub">${t.brands_label}</td><td>${t.case_count}</td><td style="text-align:right;"><span class="lnk taskRun" data-name="${t.name}">执行 ›</span></td></tr>`).join('');
  return phead('测试任务', '把用例组合成回归套件，指定 App 与品牌范围', btn('新建任务', 'ti-plus', 1, 'taskNew'))
    + `<table class="tbl"><thead><tr><th>任务名</th><th>App 范围</th><th>品牌范围</th><th>用例数</th><th></th></tr></thead><tbody>${body}</tbody></table>`;
}

export function init() {
  const el = root();
  el.querySelector('#taskNew').addEventListener('click', openNewTask);
  el.querySelectorAll('.taskRun').forEach((l) => {
    l.addEventListener('click', () => {
      store.execTask = l.dataset.name;   // 执行中心预填该任务
      store.execScript = null;           // 退出脚本模式，回到按任务执行
      go('exec');
      toast('已跳转执行中心');
    });
  });
}

/* ---------------- 新建测试任务弹窗（工作台快捷入口也会调用） ---------------- */
export function openNewTask() {
  const APPS = store.meta.apps;
  // 品牌范围只列出有台架的品牌（与原型弹窗一致：奥迪/保时捷/大众）
  const BRANDS = store.meta.device_brands;

  const html = mdHead('新建测试任务')
    + '<div class="mdlab">任务名称</div><input id="ntName" type="text" placeholder="如 V2.0 发版回归" style="width:100%;margin:5px 0 13px;">'
    + '<div class="mdlab" style="margin-bottom:6px;">App 范围 <span id="ntAc" style="color:var(--color-text-info);"></span></div>'
    + `<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 10px;border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:8px 11px;margin-bottom:13px;">${APPS.map((a) => `<label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--color-text-primary);"><input type="checkbox" class="nta" value="${a}"> ${a}</label>`).join('')}</div>`
    + '<div class="mdlab" style="margin-bottom:6px;">品牌范围 <span id="ntBc" style="color:var(--color-text-info);"></span></div>'
    + `<div style="display:flex;gap:14px;flex-wrap:wrap;border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-md);padding:8px 11px;margin-bottom:13px;">${BRANDS.map((b) => `<label style="display:flex;align-items:center;gap:7px;font-size:12px;color:var(--color-text-primary);"><input type="checkbox" class="ntb" value="${b}"> ${b}</label>`).join('')}</div>`
    + '<div style="display:flex;gap:10px;"><div style="flex:1;"><div class="mdlab">用例范围</div><select id="ntScope" style="width:100%;margin:5px 0 13px;"><option>全部用例</option><option>仅 P0</option><option>仅 P1</option></select></div><div style="flex:1;"><div class="mdlab">执行方式</div><select id="ntMode" style="width:100%;margin:5px 0 13px;"><option>多品牌并行</option><option>串行</option></select></div></div>'
    + '<div id="ntEst" class="sub" style="margin-bottom:13px;">预计用例数：0（请选择 App 与品牌）</div>'
    + `<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn"><i class="ti ti-plus" style="vertical-align:-2px;" aria-hidden="true"></i> 创建任务</button></div>`;
  const ov = openModal(html, 420);

  const selected = (cls) => Array.from(ov.querySelectorAll(`${cls}:checked`)).map((c) => c.value);
  // 已选计数 + 预估用例数（口径与原型一致：App 数 × 品牌数 × 约 5 条）
  function update() {
    const a = selected('.nta'); const b = selected('.ntb');
    ov.querySelector('#ntAc').textContent = a.length ? `已选 ${a.length}` : '';
    ov.querySelector('#ntBc').textContent = b.length ? `已选 ${b.length}` : '';
    const est = a.length * b.length * 5;
    ov.querySelector('#ntEst').textContent = `预计用例数：${est}${a.length && b.length ? `（${a.length} App × ${b.length} 品牌 × 约 5 条）` : '（请选择 App 与品牌）'}`;
  }
  ov.querySelectorAll('.nta,.ntb').forEach((c) => c.addEventListener('change', update));

  ov.querySelector('#mdOk').addEventListener('click', async () => {
    const name = ov.querySelector('#ntName').value.trim();
    const a = selected('.nta'); const b = selected('.ntb');
    if (!name) { toast('请填写任务名称'); return; }
    if (!a.length) { toast('请至少选择 1 个 App'); return; }
    if (!b.length) { toast('请至少选择 1 个品牌'); return; }
    try {
      const res = await api.post('/api/tasks', {
        name, apps: a, brands: b,
        scope: ov.querySelector('#ntScope').value, mode: ov.querySelector('#ntMode').value,
      });
      ov.remove();
      go('tasks');
      toast(`已创建任务「${name}」· 预计 ${res.count} 条用例`);
    } catch (err) { toast(err.message); }
  });

  update();
}
