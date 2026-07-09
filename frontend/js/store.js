/* 状态层：跨视图共享的内存状态（对应原型顶层变量）。
   只存「界面状态」；业务数据每次进视图时从后端拉取，保证多人操作下数据新鲜。 */

function iso(d) { return d.toISOString().slice(0, 10); }
const today = new Date();
const fiveDaysAgo = new Date(today.getTime() - 5 * 86400 * 1000);

export const store = {
  meta: { apps: [], brands: [], device_brands: [] },   // 启动时从 /api/meta 拉取
  user: { name: '张三', role: '管理员' },                 // 登录成功后覆盖

  // 测试用例页筛选（对应原型 caseFilter）
  caseFilter: { app: '全部 App', prio: '全部优先级', status: '全部状态' },

  // 报告中心筛选（对应原型 repFilter；默认近 5 天，与原型的固定日期段等价）
  repFilter: { from: iso(fiveDaysAgo), to: iso(today), app: '全部 App', brand: '全部品牌', status: '全部状态' },

  // 从任务列表点「执行 ›」带过来的预选任务名（执行中心预填）
  execTask: '',

  // 从脚本管理点「执行」带过来的脚本 {id, name}（执行中心进入脚本模式；null=按任务）
  execScript: null,
};
