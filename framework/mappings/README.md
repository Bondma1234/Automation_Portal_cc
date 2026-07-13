# mappings/ —— 功能用例映射表

维护 pytest 用例（nodeid）与官方功能用例编号的对应关系，供覆盖率盘点、
规划「下一批自动化哪些用例」以及执行结果人工核对时使用。

## ⚠ 唯一事实源是脚本里的标记

平台**只读取**用例函数上的 `@pytest.mark.case("用例编号")` 标记来建立映射
（上传 .py/.zip 时自动扫描并勾选）。本表是给人看的盘点/规划表：

- 新增覆盖时：先在用例函数上打标记，再把这一行补进 `official_case_map.csv`；
- 只改表、不打标记，平台不会识别。

## official_case_map.csv 列说明

| 列 | 含义 |
|----|------|
| case_id  | 功能用例编号，与函数上的 `@pytest.mark.case` 完全一致（官方库格式为 App 前缀 + 4 位序号，如 KW-0001） |
| nodeid   | pytest 用例路径 `文件::函数`，即标记所在的函数 |
| coverage | 该用例覆盖的功能点简述 |
| status   | automated=已自动化 / planned=已规划待编写 |
