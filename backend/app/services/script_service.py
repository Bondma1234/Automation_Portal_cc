"""脚本管理（覆盖率分子）业务逻辑：列表/上传/下载/标记扫描/脚手架打包。

映射维护：上传弹窗勾选入库（与原型一致），但选完文件后平台会扫描
文件内的 @pytest.mark.case 标记自动勾选 —— 标记即映射表，无需额外 manifest。
"""
import io
import re
import time
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .. import config, db

# 与「最近结果」列的 badge 映射：ok→通过 fail→失败 pending→待执行（前端换算）
ALLOWED_EXTS = {".py", ".zip"}

# 用例标记：@pytest.mark.case("KW-PLAY-008")（单双引号均可）
_CASE_MARK_RE = re.compile(r'@pytest\.mark\.case\(\s*["\']([^"\']+)["\']')

# zip 内单个 .py 的扫描上限（防呆：正常脚本远小于此）
_SCAN_FILE_LIMIT = 2 * 1024 * 1024


def check_size(content: bytes):
    """上传大小校验（防止大文件整包读入内存），超限抛 ValueError。"""
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"文件超过 {config.MAX_UPLOAD_MB}MB 上限")


def scan_case_marks(filename: str, content: bytes) -> list:
    """扫描 .py / .zip 内的 @pytest.mark.case 标记，返回去重保序的用例编号列表。

    只读解析、不落盘：供上传弹窗自动勾选映射（脚本标记 = 唯一事实来源）。
    """
    ext = Path(filename).suffix.lower()
    found = []
    if ext == ".py":
        found = _CASE_MARK_RE.findall(content.decode("utf-8", errors="replace"))
    elif ext == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for info in zf.infolist():
                    if not info.filename.lower().endswith(".py"):
                        continue
                    if info.file_size > _SCAN_FILE_LIMIT:
                        continue
                    text = zf.read(info).decode("utf-8", errors="replace")
                    found += _CASE_MARK_RE.findall(text)
        except zipfile.BadZipFile:
            raise ValueError("zip 文件无法解析，请检查文件是否损坏")
    seen, out = set(), []
    for cid in found:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def build_scaffold_zip() -> bytes:
    """打包框架脚手架 zip：core/config/pages/testcases 样例 + conftest/pytest.ini/requirements。

    目的：同事下载任意脚本原件后，配合本包即可在本地跑起来
    （解压 → pip install -r requirements.txt → 把脚本放进 testcases/ → pytest）。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arc in _scaffold_files():
            zf.write(path, arc)
        zf.writestr("framework/使用说明.md", _SCAFFOLD_README)
    return buf.getvalue()


# 脚手架使用说明（打包与预览共用，单一来源）
_SCAFFOLD_README = "\n".join([
    "# JDO 测试框架脚手架",
    "",
    "1. 安装依赖：`pip install -r requirements.txt`（Python 3.10+，另需本机可用 adb）；",
    "2. 连接台架：`adb connect <ip:5555>`，设备地址用环境变量 `JDO_DEVICE` 指定；",
    "   ⚠ 台架重启后先 `adb root`（SELinux 会拦截自动化端口，详见平台文档）；",
    "3. 跑样例：`cd framework && python -m pytest testcases/kuwo -v`；",
    "4. 从平台下载的脚本放进 `testcases/<模块>/`（文件名 test_ 开头）即可执行；",
    "5. 写新脚本请先读 doc/脚本框架规范.md：必须标 @pytest.mark.case、走 Page Object、先归位。",
]) + "\n"

# 预览时对文本文件读取内容的后缀白名单与大小上限
_TEXT_EXTS = {".py", ".md", ".ini", ".txt", ".cfg", ".yaml", ".yml", ".csv", ".json", ".bat"}
_PREVIEW_MAX = 200 * 1024

# 脚手架各目录说明（依《脚本框架规范》的角色分工，预览目录树里展示）
SCAFFOLD_DIR_DESC = {
    "framework": "测试框架根目录（解压后整个文件夹放到工作目录）",
    "framework/config": "框架配置：设备地址、被测包名与各模块入口 Activity",
    "framework/core": "平台组维护的底座：设备连接 / adb 封装 / 页面基类（脚本作者勿改）",
    "framework/mappings": "功能用例映射：维护 pytest nodeid 与官方功能用例编号的对应关系，供覆盖盘点与规划（平台以脚本内 @pytest.mark.case 标记为准）",
    "framework/pages": "页面对象层（Page Object）：元素定位与动作封装，脚本作者编写",
    "framework/pages/kuwo": "酷我音乐页面对象",
    "framework/testcases": "用例目录：脚本作者编写，文件名 test_ 开头",
    "framework/testcases/kuwo": "酷我音乐用例（真机验证过的样板）",
}


def _scaffold_files():
    """遍历 framework/ 下要打包的源码文件，产出 (绝对路径, zip内路径)。排除缓存/产物。"""
    root = config.FRAMEWORK_DIR
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(p in ("__pycache__", ".pytest_cache") for p in rel.parts):
            continue
        if path.is_file() and path.suffix != ".pyc":
            yield path, f"framework/{rel.as_posix()}"


def scaffold_manifest() -> list:
    """脚手架文件清单（下载前预览用）：每项 {path, size, content}。

    文本文件带内容（供弹窗点开预览），二进制/超大文件 content 为空。
    """
    items = []
    for path, arc in _scaffold_files():
        size = path.stat().st_size
        is_text = path.suffix in _TEXT_EXTS and size <= _PREVIEW_MAX
        content = path.read_text(encoding="utf-8", errors="replace") if is_text else ""
        items.append({"path": arc, "size": size, "content": content, "text": is_text})
    # 使用说明是打包时生成的虚拟文件，也纳入预览
    items.append({"path": "framework/使用说明.md",
                  "size": len(_SCAFFOLD_README.encode("utf-8")),
                  "content": _SCAFFOLD_README, "text": True})
    return items


# ---------------- 多框架预览：Zcode / Media_automation 最新上传包的目录树 ----------------

# 预览 tab 标识 → scripts.framework 值
_FW_KEYS = {"zcode": config.FRAMEWORK_ZCODE, "media": config.FRAMEWORK_MEDIA}

# 目录树里跳过的目录（版本库 / 缓存 / 运行产物，看包结构时是噪音）
_PREVIEW_SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".vscode", ".idea",
                      "output", "outputs", "logs", "allure-results", "allure-report",
                      "screenshots", "reports"}

# 两套外部框架的目录职责说明：按「目录名」匹配（无论包内嵌套层级）；"" 为整包一句话说明
_FW_DIR_DESC = {
    config.FRAMEWORK_MEDIA: {
        "": "Media_automation：ADB + XML dump 驱动（不依赖 uiautomator2），设备走 MEDIA_DEVICE_SERIAL 环境变量注入",
        "config": "配置与设备档案：settings 读 MEDIA_DEVICE_SERIAL / MEDIA_PROFILE 环境变量选台架与被测应用",
        "docs": "文档 + 官方用例映射 CSV（*mapping*.csv —— 平台覆盖率与执行映射的数据源）",
        "drivers": "驱动层：adb 命令封装与 UI XML dump 解析（点击 / 输入 / 找元素）",
        "helpers": "通用工具：等待重试 / 日志 / 文本处理",
        "pagelocators": "元素定位仓库：各页面元素的 XML 属性定位表达式",
        "pageobjects": "页面对象层：页面动作封装（组合 drivers + pagelocators）",
        "tests": "pytest 用例目录",
    },
    config.FRAMEWORK_ZCODE: {
        "": "Media_automation_Zcode：uiautomator2 驱动，设备读 config/config.yaml（平台执行前自动改写注入台架）",
        "base": "底座：uiautomator2 设备连接与基础操作封装",
        "config": "config.yaml：设备 serial / u2_ip、被测包名、超时等",
        "data": "测试数据：歌单 / 搜索关键词等",
        "docs": "文档 + 用例覆盖矩阵.md（平台映射数据源：自动化用例 ↔ 官方 Excel 编号）",
        "pages": "页面对象层（kuwo / iqiyi / ximalaya / leting）",
        "testcase": "pytest 用例：按 test_01→02→03 文件序设计，用例间有状态依赖，勿乱序执行",
        "utils": "工具：日志 / 截图 / 辅助函数",
    },
}


def _zip_member_name(info: zipfile.ZipInfo) -> str:
    """zip 成员名解码：无 UTF-8 标志位的中文名（Windows 压缩）按 cp437→GBK 还原。"""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def _decode_text(data: bytes) -> str:
    """文本内容解码：优先 UTF-8，失败退 GBK（bat / 旧编辑器保存的文件）。"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk", errors="replace")


def framework_preview(fw: str) -> dict:
    """框架预览数据（fw = jdo | zcode | media）：文件清单 + 目录说明 + 下载指向。

    - jdo：平台标准脚手架（framework/ 目录，打包下载）；
    - zcode / media：该框架**最新上传的 zip**（id 最大），直接读 zip 建树、不解压。
    找不到上传包时抛 ValueError（API 层转 404，前端在弹窗里提示）。
    """
    if fw not in _FW_KEYS:
        return {"files": scaffold_manifest(), "dirs": SCAFFOLD_DIR_DESC,
                "note": "同事下载后配合此包即可本地执行脚本（解压 → 装依赖 → 放脚本进 testcases → pytest）",
                "download_url": "/api/scripts/scaffold", "download_label": "下载脚手架 zip",
                "source": ""}
    with closing(db.get_conn()) as conn:
        row = conn.execute(
            "SELECT id, name, file_path FROM scripts"
            " WHERE framework = ? AND file_path IS NOT NULL ORDER BY id DESC LIMIT 1",
            (_FW_KEYS[fw],)).fetchone()
    if not row or not str(row["file_path"]).lower().endswith(".zip") \
            or not Path(row["file_path"]).exists():
        raise ValueError("暂无该框架的上传包 —— 请先在脚本管理上传对应 zip")

    desc_map = _FW_DIR_DESC.get(_FW_KEYS[fw], {})
    files = []
    with zipfile.ZipFile(row["file_path"]) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _zip_member_name(info)
            if any(p in _PREVIEW_SKIP_DIRS for p in name.split("/")[:-1]):
                continue
            is_text = Path(name).suffix.lower() in _TEXT_EXTS and info.file_size <= _PREVIEW_MAX
            files.append({"path": name, "size": info.file_size, "text": is_text,
                          "content": _decode_text(zf.read(info)) if is_text else ""})
    files.sort(key=lambda f: f["path"])

    # 目录说明：从文件路径归纳所有目录，按「目录名」查说明表（兼容包内有/无顶层包装目录）
    all_dirs = set()
    for f in files:
        parts = f["path"].split("/")
        for d in range(1, len(parts)):
            all_dirs.add("/".join(parts[:d]))
    dirs = {d: desc_map[d.split("/")[-1]] for d in all_dirs if d.split("/")[-1] in desc_map}

    return {"files": files, "dirs": dirs, "note": desc_map.get("", ""),
            "download_url": f"/api/scripts/{row['id']}/download",
            "download_label": "下载原包 zip", "source": row["name"]}


def list_scripts() -> list:
    """脚本列表 + 每个脚本覆盖的用例快照（行展开明细用）。新上传的排最前。"""
    with closing(db.get_conn()) as conn:
        scripts = [dict(r) for r in conn.execute("SELECT * FROM scripts ORDER BY id DESC")]
        for s in scripts:
            s["cases"] = [dict(r) for r in conn.execute(
                "SELECT case_id, module, priority FROM script_case WHERE script_id = ? ORDER BY rowid",
                (s["id"],))]
    return scripts


def save_upload(filename: str, content: bytes):
    """把上传原件存到 data/uploads/（时间戳前缀防重名），返回 Path。"""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError("仅支持 .py / .zip 文件")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved = config.UPLOAD_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{Path(filename).name}"
    saved.write_bytes(content)
    return saved


def upload(filename: str, content: bytes, name: str, app: str, version: str,
           case_ids: list, case_meta: dict) -> dict:
    """保存脚本原件并按勾选建立用例映射（我们 framework 的标准上传路径）。

    - case_ids 为前端勾选/自动识别的用例编号；
    - case_meta: {case_id: (module, priority)} 勾选用例的快照信息。
    """
    saved = save_upload(filename, content)
    with closing(db.get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO scripts(name,app,version,framework,file_name,file_path,last_result,created_at)"
            " VALUES(?,?,?,?,?,?,'pending',?)",
            (name, app, version, config.FRAMEWORK_JDO, Path(filename).name, str(saved),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        sid = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO script_case(script_id,case_id,module,priority) VALUES(?,?,?,?)",
            [(sid, cid, *case_meta.get(cid, ("", ""))) for cid in case_ids])
        conn.commit()
    return {"id": sid, "saved": saved.name, "cases": len(case_ids)}


def _make_seed_stub(script: dict, cases: list) -> str:
    """种子脚本没有原件 —— 生成一个符合《脚本框架规范》的骨架文件，保证下载按钮可用。"""
    mod = re.sub(r"\W+", "_", script["app"]).strip("_").lower() or "demo"
    lines = [
        '"""%s（v%s）—— 平台种子脚本骨架，仅示意结构。' % (script["name"], script["version"].lstrip("v")),
        "",
        "规范要点（doc/脚本框架规范.md）：",
        "1) 每条用例必须标 @pytest.mark.case(用例编号)；",
        "2) 元素定位走 Page Object，禁止在用例里写裸选择器；",
        "3) 用例开头先归位（ensure_home），不依赖上一条的残留状态。",
        '"""',
        "import pytest",
        "",
    ]
    for c in cases:
        fn = re.sub(r"\W+", "_", c["case_id"]).lower()
        lines += [
            f'@pytest.mark.case("{c["case_id"]}")',
            f"def test_{fn}({mod}):",
            f'    """{c["module"]} · {c["priority"]}"""',
            "    ...",
            "",
        ]
    return "\n".join(lines)


def get_download(script_id: int):
    """返回 (文件路径, 下载文件名)；脚本不存在返回 None。"""
    with closing(db.get_conn()) as conn:
        row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
        if not row:
            return None
        script = dict(row)
        if not script["file_path"] or not Path(script["file_path"]).exists():
            # 惰性生成种子脚本骨架并回写路径（只生成一次）
            cases = [dict(r) for r in conn.execute(
                "SELECT case_id, module, priority FROM script_case WHERE script_id = ?", (script_id,))]
            path = config.UPLOAD_DIR / f"seed_script_{script_id}.py"
            path.write_text(_make_seed_stub(script, cases), encoding="utf-8")
            conn.execute("UPDATE scripts SET file_path=?, file_name=? WHERE id=?",
                         (str(path), path.name, script_id))
            conn.commit()
            script["file_path"], script["file_name"] = str(path), path.name
    return script["file_path"], script["file_name"] or Path(script["file_path"]).name
