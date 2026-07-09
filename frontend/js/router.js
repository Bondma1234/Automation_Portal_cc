/* 路由层：侧边栏导航 + 面包屑 + 视图切换。
   每个视图模块导出 { render: async ()=>html, init: ()=>void }：
   render 负责取数并返回 HTML（对应原型的 S[key]），init 负责绑定事件（对应原型的 initX）。 */
import { root, toast } from './ui.js';
import * as dashboard from './views/dashboard.js';
import * as cases from './views/cases.js';
import * as scripts from './views/scripts.js';
import * as tasks from './views/tasks.js';
import * as exec from './views/exec.js';
import * as reports from './views/reports.js';
import * as coverage from './views/coverage.js';
import * as devices from './views/devices.js';
import * as apps from './views/apps.js';
import * as sched from './views/sched.js';
import * as settings from './views/settings.js';

// 侧边栏 5 分组 11 模块（与原型一致，顺序即展示顺序）
export const groups = [
  ['概览', [['dash', '工作台', 'ti-layout-dashboard']]],
  ['测试管理', [['cases', '测试用例', 'ti-list-check'], ['scripts', '脚本管理', 'ti-file-code'], ['tasks', '测试任务', 'ti-clipboard-list']]],
  ['执行与结果', [['exec', '执行中心', 'ti-player-play'], ['reports', '测试报告', 'ti-report'], ['cov', '覆盖率看板', 'ti-chart-bar']]],
  ['资源', [['devices', '设备管理', 'ti-devices'], ['apps', '应用管理', 'ti-apps']]],
  ['系统', [['sched', '定时调度', 'ti-clock'], ['settings', '系统设置', 'ti-settings']]],
];

const VIEWS = {
  dash: dashboard, cases, scripts, tasks, exec, reports,
  cov: coverage, devices, apps, sched, settings,
};

// key -> [分组名, 模块名]（面包屑）
const CRUMB = {};
groups.forEach(([g, items]) => items.forEach(([k, name]) => { CRUMB[k] = [g, name]; }));

let currentKey = 'dash';
export const getCurrentKey = () => currentKey;

/** 切换到模块 k：高亮侧栏 → 更新面包屑 → 渲染视图 → 绑定事件 */
export async function go(k) {
  currentKey = k;
  const el = root();
  el.querySelectorAll('.sbtn').forEach((b) => b.classList.toggle('active', b.dataset.k === k));
  const cb = el.querySelector('#crumb');
  if (cb && CRUMB[k]) {
    cb.innerHTML = `<span style="color:var(--color-text-secondary);">${CRUMB[k][0]}</span> <span style="color:var(--color-text-tertiary);">/</span> <span style="color:var(--color-text-primary);">${CRUMB[k][1]}</span>`;
  }
  const view = VIEWS[k];
  try {
    el.querySelector('#content').innerHTML = await view.render();
    if (currentKey === k) view.init();   // 渲染期间用户可能又点了别的模块，避免旧视图误绑
  } catch (err) {
    // 后端不可达时给出可操作的提示，而不是白屏
    el.querySelector('#content').innerHTML = `<div class="sub" style="padding:30px;text-align:center;">加载失败：${err.message}<br>请确认后端服务已启动（backend · 端口 8770）</div>`;
  }
}

/** 构建侧边栏导航（启动时调用一次） */
export function buildSidebar() {
  const side = root().querySelector('#side');
  groups.forEach(([label, items]) => {
    const g = document.createElement('div');
    g.className = 'glab';
    g.textContent = label;
    side.appendChild(g);
    items.forEach(([k, name, icon]) => {
      const b = document.createElement('button');
      b.className = 'sbtn';
      b.dataset.k = k;
      b.innerHTML = `<i class="ti ${icon}" style="font-size:16px;" aria-hidden="true"></i>${name}`;
      b.addEventListener('click', () => go(k));
      side.appendChild(b);
    });
  });
}
