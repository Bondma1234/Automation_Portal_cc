/* 应用管理：被测 App 的包名 / Activity / 版本 / 测试账号登记；「用例」列实时统计。
   「接入 App」弹窗风格与其它模块一致（新增用例/新建任务等，同用 ui.openModal）。 */
import { api } from '../api.js';
import { root, phead, btn, toast, mdHead, openModal } from '../ui.js';
import { go } from '../router.js';

export async function render() {
  const apps = await api.get('/api/apps');
  const rows = apps.map((a) => `<tr class="hov"><td style="font-weight:500;">${a.name}</td><td style="font-family:var(--font-mono);font-size:11px;color:var(--color-text-secondary);">${a.package}</td><td class="sub">${a.activity}</td><td>${a.version}</td><td class="sub">${a.account}</td><td>${a.case_count}</td></tr>`).join('');
  return phead('应用管理', '被测 App 的包名 / Activity / 账号 / 版本登记', btn('接入 App', 'ti-plus', 1, 'appAdd'))
    + `<table class="tbl"><thead><tr><th>App</th><th>包名</th><th>Activity</th><th>版本</th><th>测试账号</th><th>用例</th></tr></thead><tbody>${rows}</tbody></table>`;
}

export function init() {
  root().querySelector('#appAdd').addEventListener('click', openAddApp);
}

/* ---------------- 接入 App 弹窗 ---------------- */
function openAddApp() {
  const html = mdHead('接入被测 App')
    + '<div style="background:var(--color-background-tertiary);border-radius:var(--border-radius-md);padding:9px 12px;font-size:11.5px;color:var(--color-text-secondary);line-height:1.6;margin-bottom:13px;">登记被测 App 的包名与入口 Activity —— 执行时用 <code>am start</code> 拉起并注入测试账号（跨品牌不点 Launcher）。</div>'
    + '<div class="mdlab">App 名称</div><input id="apName" type="text" placeholder="如 酷我音乐" style="width:100%;margin:5px 0 12px;">'
    + '<div class="mdlab">包名</div><input id="apPkg" type="text" placeholder="如 com.jidouauto.media" style="width:100%;margin:5px 0 12px;font-family:var(--font-mono);font-size:12px;">'
    + '<div class="mdlab">入口 Activity</div><input id="apAct" type="text" placeholder="如 .ui.kuwo.main.KuwoMainActivity" style="width:100%;margin:5px 0 12px;font-family:var(--font-mono);font-size:12px;">'
    + '<div style="display:flex;gap:10px;"><div style="flex:1;"><div class="mdlab">版本</div><input id="apVer" type="text" placeholder="如 9.2.1" style="width:100%;margin:5px 0 14px;"></div><div style="flex:1;"><div class="mdlab">测试账号</div><input id="apAcc" type="text" placeholder="如 test_kuwo01" style="width:100%;margin:5px 0 14px;"></div></div>'
    + '<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="mdOk" class="pbtn"><i class="ti ti-plus" style="vertical-align:-2px;" aria-hidden="true"></i> 确定接入</button></div>';
  const ov = openModal(html, 400);

  ov.querySelector('#mdOk').addEventListener('click', async () => {
    const name = ov.querySelector('#apName').value.trim();
    const pkg = ov.querySelector('#apPkg').value.trim();
    if (!name) { toast('请填写 App 名称'); return; }
    if (!pkg) { toast('请填写包名'); return; }
    try {
      await api.post('/api/apps', {
        name, package: pkg,
        activity: ov.querySelector('#apAct').value.trim(),
        version: ov.querySelector('#apVer').value.trim() || '—',
        account: ov.querySelector('#apAcc').value.trim() || '—',
      });
      ov.remove();
      go('apps');
      toast(`已接入 App「${name}」`);
    } catch (err) { toast(err.message); }   // 「App 名称已存在」等
  });
}
