/* 登录页：覆盖整个框架的登录层（布局/文案与原型一致）。
   与原型的差异仅在于「登录」会真实调用 /api/auth/login 校验（默认 admin/123456 预填）。 */
import { api } from '../api.js';
import { root, toast } from '../ui.js';
import { theme } from '../theme.js';
import { store } from '../store.js';

export function showLogin() {
  const ov = document.createElement('div');
  ov.style.cssText = `position:absolute;inset:0;background:${theme.frame()};display:flex;align-items:center;justify-content:center;z-index:80;padding:16px;`;
  ov.innerHTML = '<div style="width:300px;max-width:90%;background:var(--color-background-primary);border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:26px 24px;text-align:center;">'
    + '<div style="width:48px;height:48px;border-radius:13px;background:var(--color-background-info);color:var(--color-text-info);display:flex;align-items:center;justify-content:center;margin:0 auto 13px;"><i class="ti ti-car" style="font-size:27px;" aria-hidden="true"></i></div>'
    + '<div style="font-size:17px;font-weight:500;color:var(--color-text-primary);">APP 测试平台</div>'
    + '<div style="font-size:12px;color:var(--color-text-secondary);margin:4px 0 22px;">车机生态自动化回归</div>'
    + '<input id="lgUser" type="text" value="admin" placeholder="账号" style="width:100%;margin-bottom:10px;">'
    + '<input id="lgPwd" type="password" value="123456" placeholder="密码" style="width:100%;margin-bottom:12px;">'
    + '<div style="display:flex;justify-content:space-between;align-items:center;font-size:11.5px;margin-bottom:18px;"><label style="display:flex;align-items:center;gap:5px;color:var(--color-text-secondary);"><input type="checkbox" checked> 记住我</label><span class="lnk">忘记密码？</span></div>'
    + '<button id="lgBtn" class="pbtn" style="width:100%;">登录</button>'
    + '<div style="font-size:10.5px;color:var(--color-text-tertiary);margin-top:14px;">© 2026 APP 车机自动化测试平台</div></div>';
  root().querySelector('#frame').appendChild(ov);

  const doLogin = async () => {
    const username = ov.querySelector('#lgUser').value.trim();
    const password = ov.querySelector('#lgPwd').value;
    try {
      const res = await api.post('/api/auth/login', { username, password });
      store.user = res.user;
      applyUser(res.user);
      ov.remove();
      toast('登录成功，欢迎回来');
    } catch (err) {
      toast(err.message);     // 「账号或密码错误」等
    }
  };
  ov.querySelector('#lgBtn').addEventListener('click', doLogin);
  ov.querySelector('#lgPwd').addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
}

/** 登录成功后更新侧栏用户区 */
function applyUser(user) {
  const el = root();
  el.querySelector('#userAvatar').textContent = user.name.slice(0, 1);
  el.querySelector('#userName').textContent = user.name;
  el.querySelector('#userRole').textContent = user.role;
}
