/* 接口层：所有后端调用的唯一入口。
   视图层不直接写 fetch —— 换后端地址/加鉴权头只改这一个文件。 */

const BASE = ''; // 同源部署（后端托管前端）；前端独立起服务调试时改成 'http://127.0.0.1:8770'

/** 统一请求：非 2xx 时抛 Error(detail)，由调用方 toast 提示 */
async function request(url, options = {}) {
  const res = await fetch(BASE + url, options);
  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* 非 JSON 响应 */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  get: (url) => request(url),
  post: (url, body) => request(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  put: (url, body) => request(url, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  /** 多部件表单（脚本上传 / Excel 导入） */
  postForm: (url, formData) => request(url, { method: 'POST', body: formData }),
  /** 触发浏览器真实下载（Excel 导出 / 模板 / 脚本下载） */
  download: (url) => {
    const a = document.createElement('a');
    a.href = BASE + url;
    document.body.appendChild(a);
    a.click();
    a.remove();
  },
};
