/* 覆盖率看板：指标卡 + 增长趋势折线（Chart.js）+ App×品牌覆盖矩阵热力图。
   配色随主题明暗切换（cc() 与原型一致）；数据由后端按真实用例/脚本/设备计算。 */
import { api } from '../api.js';
import { root, phead, mcard } from '../ui.js';
import { theme } from '../theme.js';

let data = null;   // render 取数，init 画图（Chart.js 需要元素已挂载）

export async function render() {
  data = await api.get('/api/coverage');
  const s = data.summary;
  return phead('覆盖率看板', '业务用例覆盖率 + 趋势 + App×品牌矩阵')
    + '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:10px;margin-bottom:15px;">'
    + mcard('手工回归测试点', s.total, 'ti-list-check')
    + mcard('已自动化', s.automated, 'ti-robot')
    // 全量口径（P1~P4 官方库）与 P1/P2 重点口径并列：前者诚实、后者贴合团队自动化 KPI
    + mcard('全量覆盖率', s.coverage + '%', 'ti-chart-pie')
    + mcard('P1/P2 覆盖率', s.p12_coverage + '%', 'ti-target', 'var(--color-text-success)')
    + mcard('预估节省人力', s.saved_days + ' 人天/版', 'ti-users')
    + '</div>'
    + `<div class="sub" style="margin-bottom:12px;">口径：全量 = 已自动化 ${s.automated} ÷ 官方手工用例 ${s.total}（P1~P4）；P1/P2 = ${s.p12_automated} ÷ ${s.p12_total}（团队自动化重点）</div>`
    + '<div class="sub" style="margin-bottom:5px;">覆盖率增长趋势（按版本）</div>'
    + '<div style="position:relative;width:100%;height:150px;margin-bottom:16px;"><canvas id="trendChart"></canvas></div>'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:6px;"><span class="sub">App × 品牌 覆盖矩阵</span><span style="font-size:11px;color:var(--color-text-tertiary);">数字为该格覆盖率 %</span></div>'
    + '<div id="heatmap"></div>'
    + '<div id="hmlegend" style="display:flex;gap:12px;margin-top:8px;font-size:11px;color:var(--color-text-secondary);"></div>';
}

export function init() {
  const el = root();
  const dark = theme.isDark();

  // 热力图单格配色：按覆盖率高低取色，明暗主题两套（与原型 cc() 一致）
  function cc(v) {
    if (dark) {
      if (v === 0) return ['#28333f', '#7c8a9c'];
      if (v < 45) return ['#1f5048', '#86e3d4'];
      if (v < 75) return ['#23806f', '#d6fff6'];
      return ['#2bbfa6', '#06251f'];
    }
    if (v === 0) return ['#eceae3', '#5F5E5A'];
    if (v < 45) return ['#bfe9d8', '#04342C'];
    if (v < 75) return ['#5DCAA5', '#04342C'];
    return ['#1D9E75', '#ffffff'];
  }

  // ---- 热力图 ----
  const hm = data.heatmap;
  let g = `<div style="display:grid;grid-template-columns:78px repeat(${hm.brands.length},1fr);gap:4px;font-size:12px;"><div></div>`
    + hm.brands.map((b) => `<div style="text-align:center;color:var(--color-text-secondary);">${b}</div>`).join('');
  hm.matrix.forEach((row, i) => {
    g += `<div style="display:flex;align-items:center;color:var(--color-text-secondary);">${hm.apps[i]}</div>`;
    row.forEach((v) => {
      const c = cc(v);
      g += `<div style="background:${c[0]};color:${c[1]};text-align:center;padding:7px 0;border-radius:4px;">${v === 0 ? '—' : v}</div>`;
    });
  });
  g += '</div>';
  el.querySelector('#heatmap').innerHTML = g;

  const legend = [['未覆盖', cc(0)[0]], ['低', cc(20)[0]], ['中', cc(60)[0]], ['高', cc(95)[0]]];
  el.querySelector('#hmlegend').innerHTML = legend.map(([label, color]) => `<span style="display:flex;align-items:center;gap:4px;"><span style="width:11px;height:11px;border-radius:2px;background:${color};border:0.5px solid var(--color-border-tertiary);"></span>${label}</span>`).join('');

  // ---- 趋势折线（Chart.js 已本地化到 vendor/） ----
  if (window.Chart) {
    const line = dark ? '#46c8d5' : '#0e93a0';
    const tick = dark ? '#98a4b5' : '#5c6675';
    const grid = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.07)';
    const fill = dark ? 'rgba(70,200,213,0.14)' : 'rgba(14,147,160,0.1)';
    new Chart(el.querySelector('#trendChart'), {
      type: 'line',
      data: {
        labels: data.trend.map((t) => t.version),
        datasets: [{
          data: data.trend.map((t) => t.coverage),
          borderColor: line, backgroundColor: fill, fill: true,
          tension: 0.3, pointRadius: 3, pointBackgroundColor: line,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, max: 100, ticks: { color: tick, callback: (v) => v + '%' }, grid: { color: grid } },
          x: { ticks: { color: tick }, grid: { color: grid } },
        },
      },
    });
  }
}
