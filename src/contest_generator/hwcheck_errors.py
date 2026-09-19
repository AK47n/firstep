"""硬件检测域的错误类型（工单 module-hwcheck/04 拆出来的**叶子模块**）。

## 为什么单独一个文件

`HwCheckError` 被两侧共用：

* `hwcheck.py`（检测程序渲染 + 配置形状）；
* `hwcheck_recipe.py`（库内配方加载 / 校验 / 渲染成小节）；
* `hwcheck_store.py`（落点与回读）与 `hwcheck_board.py`（板侧投影）；
* `errors.py`（`error_to_http` 表登记 → 400 中文）。

而工单 04 起 `hwcheck.py` 要**反过来** import 配方模块的渲染件（`render_main_c`
渲逐件小节），于是"异常类住在 hwcheck 里"就成了循环 import。异常类型是叶子
（它不 import 任何业务模块），把它单独放一个文件是唯一没有副作用的拆法。

**不新开第二条用户可见失败通道**：这仍然是同一个类、同一个 HTTP 400 出口，
只是从 `hwcheck` 搬到了这里；原位置继续可 import（`hwcheck` 转出）。
"""

from __future__ import annotations

__all__ = ["HwCheckError"]


class HwCheckError(Exception):
    """硬件检测域的错误（登记 errors.py → 400 中文）。

    平台词表外 / 通道开关不是布尔值 / 配方引用不存在的接口这类"请求或库内数据
    形状非法"在此抛出，路由只取参转调（对照 SkeletonError 先例，工单
    route-orchestration-homing/01）。盘侧的同类错误（父目录不存在 / 不是检测
    工程）也复用本类——同一个功能的用户可见失败面只走一条错误通道。
    """
