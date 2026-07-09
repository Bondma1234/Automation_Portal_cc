/* 主题层：「原版（浅色）/ 柔和（深色，默认）」两档切换。
   实现方式与原型一致：柔和 = 在 .jdo 上覆写 CSS 变量；原版 = 移除覆写回落到 :root。 */
import { root } from './ui.js';

const themes = [
  { label: '原版', reset: true, frame: 'var(--color-background-primary)', sidebar: 'var(--color-background-secondary)' },
  {
    label: '柔和', dark: true, frame: '#232e3d', sidebar: '#1b2431',
    vars: {
      '--color-background-primary': '#2b3646', '--color-background-secondary': '#323e4f',
      '--color-background-tertiary': '#1e2836', '--color-text-primary': '#e8edf4',
      '--color-text-secondary': '#98a4b5', '--color-text-tertiary': '#6b7889',
      '--color-border-tertiary': 'rgba(255,255,255,0.08)', '--color-border-secondary': 'rgba(255,255,255,0.15)',
      '--color-text-info': '#46c8d5', '--color-background-info': 'rgba(70,200,213,0.15)',
      '--color-border-info': 'rgba(70,200,213,0.5)', '--color-text-success': '#4dd497',
      '--color-background-success': 'rgba(77,212,151,0.16)', '--color-text-danger': '#ef7088',
      '--color-background-danger': 'rgba(239,112,136,0.16)', '--color-text-warning': '#e6b25f',
      '--color-background-warning': 'rgba(230,178,95,0.16)',
    },
  },
];

const VARKEYS = Object.keys(themes[1].vars);
const DEFAULT = 1;                       // 柔和为默认主题（既定决策）
let current = themes[DEFAULT];

export const theme = {
  /** 当前是否深色（覆盖率热力图/趋势图配色用） */
  isDark: () => !!current.dark,
  /** 当前框架背景色（登录覆盖层背景用） */
  frame: () => current.frame,
};

/** 初始化主题条；onSwitch 为切换后的重渲染回调（重画当前页，与原型一致） */
export function initThemeBar(onSwitch) {
  const bar = root().querySelector('#themebar');
  themes.forEach((t, i) => {
    const b = document.createElement('button');
    b.className = 'tbtn' + (i === DEFAULT ? ' active' : '');
    b.textContent = t.label;
    b.addEventListener('click', () => { apply(i); onSwitch(); });
    bar.appendChild(b);
  });
  apply(DEFAULT);
}

function apply(i) {
  current = themes[i];
  const el = root();
  if (current.reset) {
    VARKEYS.forEach((k) => el.style.removeProperty(k));
  } else {
    for (const k in current.vars) el.style.setProperty(k, current.vars[k]);
  }
  el.querySelector('#frame').style.background = current.frame;
  el.querySelector('#sidebar').style.background = current.sidebar;
  el.querySelectorAll('#themebar .tbtn').forEach((b, j) => b.classList.toggle('active', j === i));
}
