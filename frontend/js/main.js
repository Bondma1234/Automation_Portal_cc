/* 入口：启动顺序 = 主题 → 侧边栏 → 时钟 → 元数据 → 默认页(工作台) → 登录层。
   与原型一致：先渲染工作台再盖上登录层，登录成功后即见首页。 */
import { api } from './api.js';
import { store } from './store.js';
import { root } from './ui.js';
import { initThemeBar } from './theme.js';
import { buildSidebar, go, getCurrentKey } from './router.js';
import { showLogin } from './views/login.js';

// ---- 顶部栏实时时钟（与原型格式一致：YYYY-MM-DDTHH:mm:ss） ----
function pad(n) { return n < 10 ? '0' + n : '' + n; }
function tickClock() {
  const d = new Date();
  const s = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  const el = root().querySelector('#svcTime');
  if (el) el.textContent = s;
}

// ---- 服务状态心跳：定期探测 /api/health，异常时把「服务正常」变红 ----
async function checkHealth() {
  const dot = root().querySelector('#svcDot');
  const text = root().querySelector('#svcText');
  try {
    await api.get('/api/health');
    dot.style.background = 'var(--color-text-success)';
    text.textContent = '服务正常';
  } catch (e) {
    dot.style.background = 'var(--color-text-danger)';
    text.textContent = '服务异常';
  }
}

async function boot() {
  initThemeBar(() => go(getCurrentKey()));       // 主题切换后重画当前页（与原型一致）
  buildSidebar();
  root().querySelector('#logoutBtn').addEventListener('click', showLogin);

  setInterval(tickClock, 1000); tickClock();
  setInterval(checkHealth, 30000); checkHealth();

  try {
    const meta = await api.get('/api/meta');      // App / 品牌 下拉数据源
    Object.assign(store.meta, meta);
  } catch (e) { /* 后端未启动时视图层会给出提示 */ }

  await go('dash');
  showLogin();                                    // 首屏先见登录层（与原型一致）
}

boot();
