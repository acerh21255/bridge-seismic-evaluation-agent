# -*- coding: utf-8 -*-
"""
SAP2000 OAPI 连接驱动（参考 BridgeAgent 实战代码加固）
- 真实模式：comtypes 连接本机 SAP2000（ApplicationStart 可见启动建库 -> Hide）
- dry-run 模式：无 SAP2000 时记录全部 OAPI 调用，用于逻辑验证与演示
关键坑（来自 BridgeAgent sap_oapi.md 实战总结，均已内置处理）：
  1. InitializeNewModel 后必须 File.NewBlank，否则 Save 只写 ~6KB 空壳
  2. 隐藏态下 Save 可能只写空壳 -> 保存前短暂 Visible，保存后等文件体积稳定
  3. 保存后马上 ApplicationExit 会截断复合文档 -> 等体积稳定再退出
  4. .sdb < 32KB 视为空壳，判定失败
"""
import json
import os
import time

UNITS_KN_M = 6          # kN-m-C
MIN_SDB_BYTES = 32768   # 空模型也远大于此；~6KB 为未 NewBlank 的空壳


def _sap_ret(raw):
    """comtypes 常把 HRESULT 包成元组，只取第一个整数码。"""
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, int) and not isinstance(item, bool):
                return int(item)
        return 0
    if isinstance(raw, bool):
        return 0 if raw else 1
    if isinstance(raw, int):
        return int(raw)
    return 0


def _wait_file_stable(path, tries=25, interval=0.25):
    """等磁盘体积连续几次不变，避免 Save 未刷完就退出。"""
    last, same = -1, 0
    for _ in range(tries):
        if os.path.isfile(path):
            size = os.path.getsize(path)
            if size > 0 and size == last:
                same += 1
                if same >= 3:
                    return size
            else:
                same, last = 0, size
        time.sleep(interval)
    return os.path.getsize(path) if os.path.isfile(path) else 0


class SapDriver:
    """对 SapModel 的最小封装：链式调用 + 返回码检查 + dry-run 记录"""

    def __init__(self, dry_run=False, log_path="sap_dryrun_log.jsonl", visible=True):
        self.dry_run = dry_run
        self.log_path = log_path
        self.calls = []
        self.sap_object = None
        if dry_run:
            self.model = None
            self._log("SESSION", "dry-run 模式启动（未连接 SAP2000）")
        else:
            self._connect(visible)

    def _connect(self, visible):
        import comtypes.client
        helper = comtypes.client.CreateObject("SAP2000v1.Helper")
        helper = helper.QueryInterface(comtypes.gen.SAP2000v1.cHelper)
        self.sap_object = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
        # 先可见启动让 OLE 复合文档真正建库，随后 Hide 避免挡前台
        ret = _sap_ret(self.sap_object.ApplicationStart(UNITS_KN_M, True, ""))
        if ret != 0:
            raise RuntimeError(f"ApplicationStart 返回 {ret}")
        self.model = self.sap_object.SapModel
        if not visible:
            try:
                self.sap_object.Hide()
            except Exception:
                pass
        self._log("SESSION", "SAP2000 已启动并连接")

    def _log(self, api, detail):
        self.calls.append({"t": round(time.time(), 3), "api": api,
                           "detail": str(detail)[:500]})

    def save_log(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            for c in self.calls:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        return self.log_path

    def call(self, path, *args, ret=None):
        """path 如 "PropFrame.SetCircle"，逐层解析到 SapModel 方法并调用。"""
        self._log(path, args)
        if self.dry_run:
            return ret if ret is not None else 0
        obj = self.model
        parts = path.split(".")
        for p in parts[:-1]:
            obj = getattr(obj, p)
        result = getattr(obj, parts[-1])(*args)
        code = _sap_ret(result)
        if code != 0:
            raise RuntimeError(f"OAPI 调用失败 {path}{args} -> {result}")
        return result

    def call_tolerant(self, path, *args):
        """非关键调用：失败只记录不中断（如 SetPresentUnits/SetModifiers）。"""
        self._log(path, args)
        if self.dry_run:
            return 0
        try:
            obj = self.model
            parts = path.split(".")
            for p in parts[:-1]:
                obj = getattr(obj, p)
            return getattr(obj, parts[-1])(*args)
        except Exception:
            return None

    # ---------- 会话 ----------
    def new_model(self, units=UNITS_KN_M):
        self.call("InitializeNewModel", units, ret=0)
        # CSI 官方顺序：InitializeNewModel 之后必须 NewBlank
        self.call("File.NewBlank", ret=0)
        self.call_tolerant("SetPresentUnits", UNITS_KN_M)

    def save(self, path):
        """加固版保存：解锁 -> 删旧 -> 短暂可见 -> Save -> 等稳定 -> 复查大小。"""
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        self._log("File.Save", abs_path)
        if self.dry_run:
            return abs_path
        self.call_tolerant("SetModelIsLocked", False)
        if os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass
        size = 0
        for _attempt in (1, 2):
            try:
                self.sap_object.Visible = True   # 隐藏态可能写空壳，保存前亮一下
            except Exception:
                pass
            ret = _sap_ret(self.model.File.Save(abs_path))
            if ret != 0:
                raise RuntimeError(f"File.Save 返回 {ret}")
            size = _wait_file_stable(abs_path)
            if size >= MIN_SDB_BYTES:
                break
            time.sleep(0.4)
        try:
            self.sap_object.Hide()
        except Exception:
            pass
        if size < MIN_SDB_BYTES:
            raise RuntimeError(f"保存的 .sdb 仅 {size} 字节（空壳，疑似未 NewBlank 或被截断）")
        return abs_path

    def run_analysis(self):
        self.call("Analyse.RunAnalysis", ret=0)

    def close(self):
        log = self.save_log()
        if not self.dry_run and self.sap_object is not None:
            try:
                self.sap_object.ApplicationExit(False)
            except Exception:
                pass
            self._cleanup_temps()
        return log

    def _cleanup_temps(self):
        """Save 中断会留下 .$2k 临时文件，成功后清掉。"""
        for c in self.calls:
            if c["api"] == "File.Save":
                p = c["detail"]
                stem, _ = os.path.splitext(p)
                for extra in (stem + ".$2k", p + ".$2k"):
                    try:
                        if os.path.isfile(extra):
                            os.remove(extra)
                    except OSError:
                        pass
