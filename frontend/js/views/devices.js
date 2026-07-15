/* 设备管理：品牌台架卡片（在线 / root / udid / 分辨率 / 系统）。
   devices 表是执行设备池的单一事实源：udid 为 ip:5555 的进该品牌真机池；
   「刷新」= 后端并行 adb 探活回写；「接入台架」= 入库即可执行，无需改代码。 */
import { api } from '../api.js';
import { root, phead, btn, badge, toast, mdHead, openModal } from '../ui.js';
import { store } from '../store.js';
import { go } from '../router.js';

export async function render() {
  const devices = await api.get('/api/devices');
  const cards = devices.map((d) => {
    const m = d.meta || {};
    let extra = '';
    if (m.model) extra += `<tr><td style="padding:2px 0;">型号</td><td style="text-align:right;color:var(--color-text-primary);">${m.model}</td></tr>`;
    if (m.api) extra += `<tr><td style="padding:2px 0;">API / locale</td><td style="text-align:right;color:var(--color-text-primary);">${m.api}${m.locale ? ` · ${m.locale}` : ''}</td></tr>`;
    if (m.app_version) extra += `<tr><td style="padding:2px 0;">被测 App</td><td style="text-align:right;font-family:var(--font-mono);font-size:11px;color:var(--color-text-primary);">${m.app_version}</td></tr>`;
    return '<div class="card">'
    + `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;"><span style="font-weight:500;font-size:13px;color:var(--color-text-primary);">${d.name}</span><span style="display:flex;align-items:center;gap:6px;">${d.online ? badge('b-ok', '在线') : badge('b-fail', '离线')}<button class="iconbtn devDel" data-id="${d.id}" data-name="${d.name}" title="移除台架" aria-label="移除台架" style="font-size:12px;"><i class="ti ti-trash" aria-hidden="true"></i></button></span></div>`
    + '<table style="width:100%;font-size:12px;color:var(--color-text-secondary);">'
    + `<tr><td style="padding:2px 0;">udid</td><td style="text-align:right;font-family:var(--font-mono);font-size:11px;color:var(--color-text-primary);">${d.udid}</td></tr>`
    + `<tr><td style="padding:2px 0;">分辨率</td><td style="text-align:right;color:var(--color-text-primary);">${d.resolution}</td></tr>`
    + `<tr><td style="padding:2px 0;">系统</td><td style="text-align:right;color:var(--color-text-primary);">${d.os}</td></tr>`
    + extra
    + `<tr><td style="padding:2px 0;" title="u2 自动化的硬前提：SELinux 拦自动化端口，adbd 须为 root">root</td><td style="text-align:right;">${d.agent_ready ? badge('b-ok', '已 root') : badge('b-mut', d.online ? '非 root' : '—')}</td></tr>`
    + '</table></div>';
  }).join('');
  return phead('设备管理', '台架池即执行设备（udid 为 ip:5555 的按品牌进真机池）；刷新做真实 adb 探活',
    btn('刷新', 'ti-refresh', 0, 'devRefresh') + ' ' + btn('接入台架', 'ti-plus', 1, 'devAdd'))
    + `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:10px;">${cards}</div>`;
}

export function init() {
  const el = root();
  // 刷新 = 后端并行探活（adb connect/get-state/root 检查）并回写，数秒返回
  el.querySelector('#devRefresh').addEventListener('click', async (e) => {
    const b = e.target.closest('button');
    b.disabled = true;
    b.innerHTML = '<i class="ti ti-loader" aria-hidden="true"></i> 探测中…';
    try {
      await api.post('/api/devices/probe', {});
      toast('探活完成 · 状态已回写');
      go('devices');
    } catch (err) { toast(err.message); b.disabled = false; }
  });
  el.querySelector('#devAdd').addEventListener('click', openAddDevice);
  el.querySelectorAll('.devDel').forEach((b) => {
    b.addEventListener('click', async () => {
      if (!window.confirm(`确定移除台架「${b.dataset.name}」？将退出该品牌执行池。`)) return;
      try {
        await api.del(`/api/devices/${b.dataset.id}`);
        toast('台架已移除');
        go('devices');
      } catch (err) { toast(err.message); }
    });
  });
}

/* 接入台架弹窗：入库即进该品牌执行池（保存后自动探活一次） */
function openAddDevice() {
  const brands = store.meta.device_brands;
  const html = mdHead('接入台架')
    + '<div class="mdlab">台架名称</div><input id="dvName" type="text" placeholder="如 奥迪 MMI 台架 #3" style="width:100%;margin:5px 0 13px;">'
    + `<div style="display:flex;gap:10px;"><div style="width:110px;"><div class="mdlab">品牌</div><select id="dvBrand" style="width:100%;margin:5px 0 13px;">${brands.map((b) => `<option>${b}</option>`).join('')}</select></div><div style="flex:1;min-width:0;"><div class="mdlab">台架地址（adb serial，如 192.168.2.99:5555）</div><input id="dvUdid" type="text" placeholder="ip:5555" style="width:100%;margin:5px 0 13px;font-family:var(--font-mono);"></div></div>`
    + '<div style="display:flex;gap:10px;"><div style="flex:1;"><div class="mdlab">分辨率</div><input id="dvRes" type="text" placeholder="1920×816" style="width:100%;margin:5px 0 15px;"></div><div style="flex:1;"><div class="mdlab">系统</div><input id="dvOs" type="text" placeholder="Android 14 (AAOS)" style="width:100%;margin:5px 0 15px;"></div></div>'
    + '<div class="sub" style="margin-bottom:12px;font-size:11.5px;">保存后自动探活一次；地址为 ip:5555 格式的台架会进入该品牌的真机执行池（同品牌多台架执行时自动挑空闲的）。</div>'
    + '<div style="display:flex;justify-content:flex-end;gap:8px;"><button id="mdCancel" class="gbtn">取消</button><button id="dvOk" class="pbtn"><i class="ti ti-plus" style="vertical-align:-2px;" aria-hidden="true"></i> 接入</button></div>';
  const ov = openModal(html, 430);
  ov.querySelector('#dvOk').addEventListener('click', async () => {
    const name = ov.querySelector('#dvName').value.trim();
    const udid = ov.querySelector('#dvUdid').value.trim();
    if (!name) { toast('请填写台架名称'); return; }
    if (!udid) { toast('请填写台架地址（adb serial）'); return; }
    const okBtn = ov.querySelector('#dvOk');
    okBtn.disabled = true;
    try {
      await api.post('/api/devices', {
        name, udid,
        brand: ov.querySelector('#dvBrand').value,
        resolution: ov.querySelector('#dvRes').value.trim() || '—',
        os: ov.querySelector('#dvOs').value.trim() || '—',
      });
      ov.remove();
      go('devices');
      toast(`台架「${name}」已接入 · 已探活`);
    } catch (err) { toast(err.message); okBtn.disabled = false; }
  });
}
