"""Tkinter GUI for WGS84 / CGCS2000 coordinate and velocity conversion."""

import tkinter as tk
from tkinter import messagebox, ttk

from .conversions import (
    HelmertParams,
    blh_to_xyz,
    helmert_forward,
    helmert_inverse,
    velocity_ecef_to_enu,
    velocity_enu_to_ecef,
    xyz_to_blh,
)
from .ellipsoids import ELLIPSOIDS

DATUMS = ("WGS84", "CGCS2000")


def _parse_float(entry: ttk.Entry, field_name: str) -> float:
    text = entry.get().strip()
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"“{field_name}” 不是合法的数字：{text!r}")


class LabeledEntry(ttk.Frame):
    """A label + entry pair laid out on a single grid row."""

    def __init__(self, parent, label, row, column=0, width=22, default=""):
        super().__init__(parent)
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=(0, 6), pady=3)
        self.var = tk.StringVar(value=default)
        self.entry = ttk.Entry(parent, textvariable=self.var, width=width)
        self.entry.grid(row=row, column=column + 1, sticky="w", pady=3)

    def get_float(self, field_name: str) -> float:
        return _parse_float(self.entry, field_name)

    def set(self, value):
        self.var.set(value)


class DatumConversionTab(ttk.Frame):
    """WGS84 <-> CGCS2000 datum conversion, with BLH or XYZ as input."""

    def __init__(self, parent, get_helmert_params):
        super().__init__(parent, padding=16)
        self.get_helmert_params = get_helmert_params
        self._build()

    def _build(self):
        src_frame = ttk.LabelFrame(self, text="源坐标", padding=12)
        src_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        ttk.Label(src_frame, text="源坐标系:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.src_datum = tk.StringVar(value="WGS84")
        ttk.Combobox(src_frame, textvariable=self.src_datum, values=DATUMS,
                     state="readonly", width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(src_frame, text="输入格式:").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 6))
        self.src_format = tk.StringVar(value="BLH")
        fmt_frame = ttk.Frame(src_frame)
        fmt_frame.grid(row=1, column=1, sticky="w", pady=(6, 6))
        ttk.Radiobutton(fmt_frame, text="纬度/经度/大地高 (BLH)", variable=self.src_format,
                         value="BLH", command=self._refresh_input_labels).pack(anchor="w")
        ttk.Radiobutton(fmt_frame, text="地心直角坐标 (XYZ)", variable=self.src_format,
                         value="XYZ", command=self._refresh_input_labels).pack(anchor="w")

        ttk.Separator(src_frame, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)

        self.label1 = ttk.Label(src_frame, text="纬度 B (度):")
        self.label1.grid(row=3, column=0, sticky="w", padx=(0, 6), pady=3)
        self.entry1 = ttk.Entry(src_frame, width=22)
        self.entry1.grid(row=3, column=1, sticky="w", pady=3)

        self.label2 = ttk.Label(src_frame, text="经度 L (度):")
        self.label2.grid(row=4, column=0, sticky="w", padx=(0, 6), pady=3)
        self.entry2 = ttk.Entry(src_frame, width=22)
        self.entry2.grid(row=4, column=1, sticky="w", pady=3)

        self.label3 = ttk.Label(src_frame, text="大地高 H (米):")
        self.label3.grid(row=5, column=0, sticky="w", padx=(0, 6), pady=3)
        self.entry3 = ttk.Entry(src_frame, width=22)
        self.entry3.grid(row=5, column=1, sticky="w", pady=3)

        ttk.Label(src_frame, text="目标坐标系:").grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(12, 3))
        self.dst_datum = tk.StringVar(value="CGCS2000")
        ttk.Combobox(src_frame, textvariable=self.dst_datum, values=DATUMS,
                     state="readonly", width=12).grid(row=6, column=1, sticky="w", pady=(12, 3))

        ttk.Button(src_frame, text="转换 →", command=self._convert).grid(
            row=7, column=0, columnspan=2, pady=(14, 0))

        out_frame = ttk.LabelFrame(self, text="目标坐标结果", padding=12)
        out_frame.grid(row=0, column=1, sticky="nsew")

        self.out_vars = {}
        rows = [
            ("blh_b", "纬度 B (度):"),
            ("blh_l", "经度 L (度):"),
            ("blh_h", "大地高 H (米):"),
            ("sep", None),
            ("xyz_x", "X (米):"),
            ("xyz_y", "Y (米):"),
            ("xyz_z", "Z (米):"),
        ]
        r = 0
        for key, text in rows:
            if key == "sep":
                ttk.Separator(out_frame, orient="horizontal").grid(
                    row=r, column=0, columnspan=2, sticky="ew", pady=8)
                r += 1
                continue
            ttk.Label(out_frame, text=text).grid(row=r, column=0, sticky="w", padx=(0, 6), pady=3)
            var = tk.StringVar(value="—")
            self.out_vars[key] = var
            ttk.Entry(out_frame, textvariable=var, width=24, state="readonly").grid(
                row=r, column=1, sticky="w", pady=3)
            r += 1

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self._refresh_input_labels()

    def _refresh_input_labels(self):
        if self.src_format.get() == "BLH":
            self.label1.config(text="纬度 B (度):")
            self.label2.config(text="经度 L (度):")
            self.label3.config(text="大地高 H (米):")
        else:
            self.label1.config(text="X (米):")
            self.label2.config(text="Y (米):")
            self.label3.config(text="Z (米):")

    def _convert(self):
        try:
            src_datum = self.src_datum.get()
            dst_datum = self.dst_datum.get()
            src_ellip = ELLIPSOIDS[src_datum]
            dst_ellip = ELLIPSOIDS[dst_datum]

            v1 = _parse_float(self.entry1, "第一个输入值")
            v2 = _parse_float(self.entry2, "第二个输入值")
            v3 = _parse_float(self.entry3, "第三个输入值")

            if self.src_format.get() == "BLH":
                x, y, z = blh_to_xyz(v1, v2, v3, src_ellip)
            else:
                x, y, z = v1, v2, v3

            if src_datum != dst_datum:
                params = self.get_helmert_params()
                if src_datum == "WGS84" and dst_datum == "CGCS2000":
                    x, y, z = helmert_forward(x, y, z, params)
                elif src_datum == "CGCS2000" and dst_datum == "WGS84":
                    x, y, z = helmert_inverse(x, y, z, params)

            lat, lon, h = xyz_to_blh(x, y, z, dst_ellip)

            self.out_vars["blh_b"].set(f"{lat:.9f}")
            self.out_vars["blh_l"].set(f"{lon:.9f}")
            self.out_vars["blh_h"].set(f"{h:.4f}")
            self.out_vars["xyz_x"].set(f"{x:.4f}")
            self.out_vars["xyz_y"].set(f"{y:.4f}")
            self.out_vars["xyz_z"].set(f"{z:.4f}")
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
        except Exception as exc:  # noqa: BLE001 - surface unexpected math errors to the user
            messagebox.showerror("转换失败", str(exc))


class VelocityConversionTab(ttk.Frame):
    """ECEF position+velocity <-> geodetic position + ENU velocity."""

    DIR_ECEF_TO_ENU = "ecef2enu"
    DIR_ENU_TO_ECEF = "enu2ecef"

    def __init__(self, parent):
        super().__init__(parent, padding=16)
        self._build()

    def _build(self):
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(ctrl_frame, text="参考椭球:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.ellip_name = tk.StringVar(value="CGCS2000")
        ttk.Combobox(ctrl_frame, textvariable=self.ellip_name, values=DATUMS,
                     state="readonly", width=12).grid(row=0, column=1, sticky="w")

        self.direction = tk.StringVar(value=self.DIR_ECEF_TO_ENU)
        dir_frame = ttk.Frame(self)
        dir_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Radiobutton(dir_frame, text="地心系位置/速度 → 大地坐标 + 东北天速度",
                         variable=self.direction, value=self.DIR_ECEF_TO_ENU,
                         command=self._refresh_visible_inputs).pack(anchor="w")
        ttk.Radiobutton(dir_frame, text="大地坐标 + 东北天速度 → 地心系位置/速度",
                         variable=self.direction, value=self.DIR_ENU_TO_ECEF,
                         command=self._refresh_visible_inputs).pack(anchor="w")

        # --- input: ECEF position + velocity ---
        self.frame_ecef_in = ttk.LabelFrame(self, text="输入：地心系位置与速度", padding=12)
        self.x_in = LabeledEntry(self.frame_ecef_in, "X (米):", 0)
        self.y_in = LabeledEntry(self.frame_ecef_in, "Y (米):", 1)
        self.z_in = LabeledEntry(self.frame_ecef_in, "Z (米):", 2)
        self.vx_in = LabeledEntry(self.frame_ecef_in, "VX (米/秒):", 3)
        self.vy_in = LabeledEntry(self.frame_ecef_in, "VY (米/秒):", 4)
        self.vz_in = LabeledEntry(self.frame_ecef_in, "VZ (米/秒):", 5)

        # --- input: geodetic position + ENU velocity ---
        self.frame_enu_in = ttk.LabelFrame(self, text="输入：大地坐标与东北天速度", padding=12)
        self.b_in = LabeledEntry(self.frame_enu_in, "纬度 B (度):", 0)
        self.l_in = LabeledEntry(self.frame_enu_in, "经度 L (度):", 1)
        self.h_in = LabeledEntry(self.frame_enu_in, "大地高 H (米):", 2)
        self.ve_in = LabeledEntry(self.frame_enu_in, "东向速度 VE (米/秒):", 3)
        self.vn_in = LabeledEntry(self.frame_enu_in, "北向速度 VN (米/秒):", 4)
        self.vu_in = LabeledEntry(self.frame_enu_in, "天向速度 VU (米/秒):", 5)

        self.frame_ecef_in.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        self.frame_enu_in.grid(row=2, column=0, sticky="nsew", padx=(0, 12))

        ttk.Button(self, text="转换 →", command=self._convert).grid(row=3, column=0, sticky="w", pady=(14, 0))

        out_frame = ttk.LabelFrame(self, text="输出结果", padding=12)
        out_frame.grid(row=2, column=1, rowspan=2, sticky="nsew")
        self.out_vars = {}
        rows = [
            ("blh_b", "纬度 B (度):"),
            ("blh_l", "经度 L (度):"),
            ("blh_h", "大地高 H (米):"),
            ("v_e", "东向速度 VE (米/秒):"),
            ("v_n", "北向速度 VN (米/秒):"),
            ("v_u", "天向速度 VU (米/秒):"),
            ("sep", None),
            ("xyz_x", "X (米):"),
            ("xyz_y", "Y (米):"),
            ("xyz_z", "Z (米):"),
            ("v_x", "VX (米/秒):"),
            ("v_y", "VY (米/秒):"),
            ("v_z", "VZ (米/秒):"),
        ]
        r = 0
        for key, text in rows:
            if key == "sep":
                ttk.Separator(out_frame, orient="horizontal").grid(
                    row=r, column=0, columnspan=2, sticky="ew", pady=8)
                r += 1
                continue
            ttk.Label(out_frame, text=text).grid(row=r, column=0, sticky="w", padx=(0, 6), pady=3)
            var = tk.StringVar(value="—")
            self.out_vars[key] = var
            ttk.Entry(out_frame, textvariable=var, width=26, state="readonly").grid(
                row=r, column=1, sticky="w", pady=3)
            r += 1

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self._refresh_visible_inputs()

    def _refresh_visible_inputs(self):
        if self.direction.get() == self.DIR_ECEF_TO_ENU:
            self.frame_enu_in.grid_remove()
            self.frame_ecef_in.grid()
        else:
            self.frame_ecef_in.grid_remove()
            self.frame_enu_in.grid()

    def _convert(self):
        try:
            ellip = ELLIPSOIDS[self.ellip_name.get()]

            if self.direction.get() == self.DIR_ECEF_TO_ENU:
                x = self.x_in.get_float("X")
                y = self.y_in.get_float("Y")
                z = self.z_in.get_float("Z")
                vx = self.vx_in.get_float("VX")
                vy = self.vy_in.get_float("VY")
                vz = self.vz_in.get_float("VZ")

                lat, lon, h = xyz_to_blh(x, y, z, ellip)
                ve, vn, vu = velocity_ecef_to_enu(vx, vy, vz, lat, lon)

                self.out_vars["blh_b"].set(f"{lat:.9f}")
                self.out_vars["blh_l"].set(f"{lon:.9f}")
                self.out_vars["blh_h"].set(f"{h:.4f}")
                self.out_vars["v_e"].set(f"{ve:.6f}")
                self.out_vars["v_n"].set(f"{vn:.6f}")
                self.out_vars["v_u"].set(f"{vu:.6f}")
                for k in ("xyz_x", "xyz_y", "xyz_z", "v_x", "v_y", "v_z"):
                    self.out_vars[k].set("—")
            else:
                lat = self.b_in.get_float("纬度 B")
                lon = self.l_in.get_float("经度 L")
                h = self.h_in.get_float("大地高 H")
                ve = self.ve_in.get_float("东向速度 VE")
                vn = self.vn_in.get_float("北向速度 VN")
                vu = self.vu_in.get_float("天向速度 VU")

                x, y, z = blh_to_xyz(lat, lon, h, ellip)
                vx, vy, vz = velocity_enu_to_ecef(ve, vn, vu, lat, lon)

                self.out_vars["xyz_x"].set(f"{x:.4f}")
                self.out_vars["xyz_y"].set(f"{y:.4f}")
                self.out_vars["xyz_z"].set(f"{z:.4f}")
                self.out_vars["v_x"].set(f"{vx:.6f}")
                self.out_vars["v_y"].set(f"{vy:.6f}")
                self.out_vars["v_z"].set(f"{vz:.6f}")
                for k in ("blh_b", "blh_l", "blh_h", "v_e", "v_n", "v_u"):
                    self.out_vars[k].set("—")
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("转换失败", str(exc))


class SettingsTab(ttk.Frame):
    """Ellipsoid reference info and editable Helmert datum parameters."""

    def __init__(self, parent):
        super().__init__(parent, padding=16)
        self.params = HelmertParams()
        self._build()

    def _build(self):
        ellip_frame = ttk.LabelFrame(self, text="椭球参数（只读）", padding=12)
        ellip_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        r = 0
        for name in DATUMS:
            e = ELLIPSOIDS[name]
            ttk.Label(ellip_frame, text=f"{name}:", font=("", 10, "bold")).grid(
                row=r, column=0, sticky="w", pady=(6, 0))
            r += 1
            ttk.Label(ellip_frame, text=f"  长半轴 a = {e.a:.4f} 米").grid(row=r, column=0, sticky="w")
            r += 1
            ttk.Label(ellip_frame, text=f"  扁率倒数 1/f = {e.inv_f}").grid(row=r, column=0, sticky="w")
            r += 1
            ttk.Label(ellip_frame, text=f"  第一偏心率平方 e² = {e.e2:.12f}").grid(row=r, column=0, sticky="w")
            r += 1

        helmert_frame = ttk.LabelFrame(
            self, text="WGS84 → CGCS2000 七参数 (Bursa-Wolf)", padding=12)
        helmert_frame.grid(row=0, column=1, sticky="nsew")

        note = ("默认全部为 0：WGS84 与 CGCS2000 均对齐 ITRF 框架，在常规测绘精度下\n"
                "视为重合（实际差异一般在厘米级以下）。如你持有特定区域的转换参数，\n"
                "可在下方填入后点击应用。")
        ttk.Label(helmert_frame, text=note, foreground="#555555", justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.entries = {}
        fields = [
            ("dx", "ΔX 平移 (米)"),
            ("dy", "ΔY 平移 (米)"),
            ("dz", "ΔZ 平移 (米)"),
            ("rx", "Rx 旋转 (角秒)"),
            ("ry", "Ry 旋转 (角秒)"),
            ("rz", "Rz 旋转 (角秒)"),
            ("ds", "尺度差 (ppm)"),
        ]
        for i, (key, label) in enumerate(fields, start=1):
            le = LabeledEntry(helmert_frame, label + ":", i, default="0.0")
            self.entries[key] = le

        btn_frame = ttk.Frame(helmert_frame)
        btn_frame.grid(row=len(fields) + 1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_frame, text="应用参数", command=self._apply).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="恢复默认 (全 0)", command=self._reset).pack(side="left")

        self.status_var = tk.StringVar(value="当前使用：全 0（视为重合）")
        ttk.Label(helmert_frame, textvariable=self.status_var, foreground="#2a7a2a").grid(
            row=len(fields) + 2, column=0, columnspan=2, pady=(8, 0), sticky="w")

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _apply(self):
        try:
            values = {key: le.get_float(key) for key, le in self.entries.items()}
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
            return
        self.params = HelmertParams(**values)
        self.status_var.set("当前使用：自定义参数（已应用）")

    def _reset(self):
        for le in self.entries.values():
            le.set("0.0")
        self.params = HelmertParams()
        self.status_var.set("当前使用：全 0（视为重合）")

    def get_params(self) -> HelmertParams:
        return self.params


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TransPos - WGS84 / CGCS2000 坐标转换工具")
        self.geometry("880x560")
        self.minsize(820, 520)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.settings_tab = SettingsTab(notebook)
        self.datum_tab = DatumConversionTab(notebook, self.settings_tab.get_params)
        self.velocity_tab = VelocityConversionTab(notebook)

        notebook.add(self.datum_tab, text="坐标转换")
        notebook.add(self.velocity_tab, text="位置/速度转换")
        notebook.add(self.settings_tab, text="参数设置")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
