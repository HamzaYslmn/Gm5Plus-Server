#!/data/data/com.termux/files/usr/bin/python
# GM5 Plus sistem panosu + kontrol.  `system`  = Textual TUI (izleme + flash/LED/titresim kontrol).
# `system --no-tui`  = normal shell ANSI pano.  `system --once` = tek kare (shell).
# Veri: /sys + /proc (anlik) + termux-sensor (arka plan). Kontrol: su (Magisk) + termux-api.
import os, sys, time, glob, json, re, math, subprocess, threading, signal
from collections import deque

# ============================== COLLECTORS (paylasimli) ==============================
def read(path, d=""):
    try:
        with open(path) as f: return f.read().strip()
    except Exception: return d
def ri(path, d=0):
    try: return int(read(path))
    except Exception: return d
def _zt(x): return x / 1000.0 if abs(x) >= 1000 else float(x)

def thermal_rows():                              # [(type, °C)] tum bolgeler
    out = []
    for z in glob.glob("/sys/class/thermal/thermal_zone*"):
        t = read(z + "/type"); v = ri(z + "/temp")
        if t and v: out.append((t, _zt(v)))
    return sorted(out, key=lambda x: -x[1])

def cpu_temps():
    cpu, pm = [], None
    for t, x in thermal_rows():
        if t.startswith("tsens_tz_sensor"): cpu.append(x)
        elif t == "pm8950_tz": pm = x
    return (sum(cpu) / len(cpu) if cpu else 0.0), (max(cpu) if cpu else 0.0), pm

def online_cpus():                               # gercekten acik cekirdekler (sysfs)
    s = read("/sys/devices/system/cpu/online", "")
    out = set()
    for part in s.split(","):
        if "-" in part:
            try: a, b = part.split("-"); out.update(range(int(a), int(b) + 1))
            except Exception: pass
        elif part.strip():
            try: out.add(int(part))
            except Exception: pass
    return out

_pstat = {}
def cpu_stats():
    # SADECE sysfs'e gore online cekirdekleri say. Offline cekirdekler (orn cpu3) bu
    # kernelde /proc/stat'ta sahte ~1.5M idle tick biriktirip aggregate'i %0'a cekiyor.
    on = online_cpus(); per, busy_sum, tot_sum = [], 0, 0
    for line in read("/proc/stat").splitlines():
        p = line.split()
        if not p or not p[0].startswith("cpu") or p[0] == "cpu": continue
        try: n = int(p[0][3:]); v = list(map(int, p[1:8]))
        except Exception: continue
        idle = v[3] + v[4]; total = sum(v)
        pt, pi = _pstat.get(n, (total, idle)); _pstat[n] = (total, idle)
        dt, di = total - pt, idle - pi
        if (n in on) and dt > 0:
            frac = max(0.0, min(1.0, 1 - di / dt))
            per.append((n, frac, True)); busy_sum += dt - di; tot_sum += dt
        else:
            per.append((n, 0.0, False))
    per.sort()
    return (busy_sum / tot_sum if tot_sum > 0 else 0.0), per

KGSL = "/sys/class/kgsl/kgsl-3d0/"
def gpu_info():
    frac = 0.0
    try:
        b, tot = map(int, read(KGSL + "gpubusy").split()); frac = b / tot if tot else 0.0
    except Exception: pass
    cur = ri(KGSL + "devfreq/cur_freq") or ri(KGSL + "gpuclk")
    mx = ri(KGSL + "devfreq/max_freq") or ri(KGSL + "max_gpuclk")
    return frac, cur, mx

def battery():
    b = "/sys/class/power_supply/battery/"
    cap = ri(b + "capacity"); status = read(b + "status", "?"); health = read(b + "health", "?")
    temp = ri(b + "temp"); temp = temp / 10.0 if abs(temp) >= 100 else float(temp)
    volt = ri(b + "voltage_now"); volt = volt / 1e6 if volt > 100000 else volt / 1000.0
    cur = ri(b + "current_now"); cur = cur / 1000.0 if abs(cur) >= 1000 else float(cur)
    return cap, status, health, temp, volt, cur

_net = {"t": 0.0}
def net_rate():
    rx = ri("/sys/class/net/wlan0/statistics/rx_bytes"); tx = ri("/sys/class/net/wlan0/statistics/tx_bytes")
    now = time.monotonic(); dt = (now - _net["t"]) or 1.0
    rr = max(0.0, (rx - _net.get("rx", rx)) / dt); tr = max(0.0, (tx - _net.get("tx", tx)) / dt)
    _net.update(rx=rx, tx=tx, t=now); return rr, tr, rx, tx
def wifi_link():
    for line in read("/proc/net/wireless").splitlines():
        s = line.split()
        if s and s[0] == "wlan0:":
            try: return float(s[2].rstrip(".")), float(s[3].rstrip("."))
            except Exception: break
    return None, None
def disk_free(path="/data"):
    try:
        s = os.statvfs(path); tot = s.f_blocks * s.f_frsize
        return tot, tot - s.f_bavail * s.f_frsize, s.f_bavail * s.f_frsize
    except Exception: return 0, 0, 0
def human(b):
    b = float(b)
    for u in ("B", "K", "M", "G", "T"):
        if b < 1024: return ("%.0f%s" if u in "BK" else "%.1f%s") % (b, u)
        b /= 1024
    return "%.1fP" % b


# --- android sensors (termux-api, arka plan) ---
SDATA = {}; SERR = ["yukleniyor"]
def sensor_reader(delay=2000):                       # 2sn (yuku azalt; bu CPU yavas)
    try:
        p = subprocess.Popen(["termux-sensor", "-a", "-d", str(delay)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except Exception:
        SERR[0] = "termux-api yok"; return
    buf, depth = "", 0
    for line in p.stdout:
        buf += line; depth += line.count("{") - line.count("}")
        if depth <= 0 and buf.strip():
            try:
                obj = json.loads(buf)
                for k, v in obj.items():
                    if isinstance(v, dict) and "values" in v: SDATA[k] = v["values"]
                SERR[0] = ""
            except Exception: pass
            buf, depth = "", 0

def norm_name(name):
    nl = re.sub(r"[-_ ]*\b(non[- ]?wakeup|wake[- ]?up|wakeup|uncalibrated|secondary)\b[-_ ]*", " ", name.lower())
    return re.sub(r"\s+", " ", nl).strip(" -_")
def variant_rank(name):
    nl = name.lower()
    return (("uncalib" in nl) + ("wake" in nl) + ("secondary" in nl) + ("dummy" in nl), len(name))
def sensor_units(name, vals):
    nl = name.lower()
    if not isinstance(vals, list) or not vals: return str(vals), ""
    a3 = "  ".join("%+.2f" % x for x in vals[:3])
    if "gyro" in nl: return a3, "rad/s"
    if "accel" in nl or "linear" in nl: return a3, "m/s²"
    if "gravity" in nl: return a3, "m/s²"
    if "magn" in nl or "mmc" in nl: return a3, "µT"
    if "light" in nl or "als" in nl or "ltr" in nl: return "%.1f" % vals[0], "lux"
    if "prox" in nl: return "%.1f" % vals[0], "cm"
    if "step" in nl: return "%.0f" % vals[0], "adim"
    if "orient" in nl: return a3, "°"
    if "rotat" in nl or "game" in nl: return "  ".join("%+.2f" % x for x in vals[:4]), "quat"
    return "  ".join("%+.2f" % x for x in vals[:4]), ""
def merged_sensors():
    best = {}
    for k, v in SDATA.items():
        nk, rk = norm_name(k), variant_rank(k)
        if nk not in best or rk < best[nk][0]: best[nk] = (rk, k, v)
    return [(k, v) for _, k, v in sorted(best.values(), key=lambda r: r[1].lower())]

def derived_rows():                              # pusula (manyetometre) + yukseklik (basinc)
    byq = {}
    for k, v in merged_sensors():
        nl = k.lower()
        if ("magn" in nl or "mmc" in nl) and "magn" not in byq: byq["magn"] = v
        if ("pressure" in nl or "baro" in nl) and "pressure" not in byq: byq["pressure"] = v
    out = []
    if byq.get("magn") and len(byq["magn"]) >= 2:
        az = math.degrees(math.atan2(-byq["magn"][1], byq["magn"][0])) % 360
        out.append(("Pusula", "%.0f" % az, "°"))
    if byq.get("pressure"):
        alt = 44330.0 * (1 - (byq["pressure"][0] / 1013.25) ** 0.1903)
        out.append(("Yukseklik", "%.0f" % alt, "m"))
    return out

# --- multitouch + hall (root: getevent) ---
TOUCH = {"slots": {}, "last": (0, 0), "ok": False, "err": "root/getevent bekleniyor"}
def touch_reader():
    try:
        p = subprocess.Popen(["su", "-c", "getevent -l /dev/input/event0"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except Exception: return
    cur = [0]
    for line in p.stdout:
        f = line.split()
        if len(f) < 3: continue
        code, val = f[-2], f[-1]
        try:
            if code == "ABS_MT_SLOT": cur[0] = int(val, 16)
            elif code == "ABS_MT_TRACKING_ID":
                if val == "ffffffff": TOUCH["slots"].pop(cur[0], None)
                else: TOUCH["slots"].setdefault(cur[0], {"x": 0, "y": 0})
                TOUCH["ok"] = True
            elif code == "ABS_MT_POSITION_X":
                d = TOUCH["slots"].setdefault(cur[0], {"x": 0, "y": 0}); d["x"] = int(val, 16); TOUCH["last"] = (d["x"], d["y"]); TOUCH["ok"] = True
            elif code == "ABS_MT_POSITION_Y":
                d = TOUCH["slots"].setdefault(cur[0], {"x": 0, "y": 0}); d["y"] = int(val, 16); TOUCH["last"] = (d["x"], d["y"]); TOUCH["ok"] = True
        except Exception: pass
HALL = {"closed": False, "ok": False}
def hall_reader():
    try:
        p = subprocess.Popen(["su", "-c", "getevent -l /dev/input/event3"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except Exception: return
    for line in p.stdout:
        f = line.split()
        if len(f) < 3: continue
        code, val = f[-2], f[-1]
        if code == "KEY_SLEEP" and val == "00000001": HALL["closed"] = True; HALL["ok"] = True
        elif code == "KEY_WAKEUP" and val == "00000001": HALL["closed"] = False; HALL["ok"] = True

# ============================== CONTROL (root + termux-api) ==============================
LED = "/sys/class/leds"
def su(cmd):                                     # fire-and-forget (Textual'i bloklamaz)
    try: subprocess.Popen(["su", "-c", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass
def flash_on(n=120):
    su("echo %d > %s/led:torch_0/brightness; echo %d > %s/led:torch_1/brightness; echo 2 > %s/led:switch/brightness" % (n, LED, n, LED, LED))
def flash_off():
    su("echo 0 > %s/led:switch/brightness; echo 0 > %s/led:torch_0/brightness; echo 0 > %s/led:torch_1/brightness" % (LED, LED, LED))
def flash_is_on(): return read(LED + "/led:switch/brightness", "0") != "0"
def led_rgb(r, g, b):
    su("echo %d > %s/red/brightness; echo %d > %s/green/brightness; echo %d > %s/blue/brightness" % (r, LED, g, LED, b, LED))
def vibrate(ms=200):
    try: subprocess.Popen(["termux-vibrate", "-f", "-d", str(ms)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

# ============================== SHELL UI (--no-tui) — ANSI pano ==============================
E = "\033"; ANSI = re.compile(r"\033\[[0-9;]*m")
def sgr(s, *c): return E + "[" + ";".join(c) + "m" + s + E + "[0m"
BOLD, DIM = "1", "2"
RED, GRN, YEL, MAG, CYN, WHT = "31", "32", "33", "35", "36", "37"
BRED, BGRN, BYEL, BMAG, BCYN = "91", "92", "93", "95", "96"
def tcol(t): return CYN if t < 38 else GRN if t < 48 else BGRN if t < 58 else YEL if t < 68 else BYEL if t < 76 else BRED
def abar(frac, w=18, col=GRN):
    frac = max(0.0, min(1.0, frac)); f = int(round(frac * w))
    return sgr("█" * f, col) + sgr("░" * (w - f), DIM)
def vis(s): return len(ANSI.sub("", s))
def clip(s, w):
    if vis(s) <= w: return s
    out, n, i = [], 0, 0
    while i < len(s) and n < w:
        m = ANSI.match(s, i)
        if m: out.append(m.group()); i = m.end(); continue
        out.append(s[i]); n += 1; i += 1
    return "".join(out) + E + "[0m"
def hr(title, w): return sgr("── ", DIM) + sgr(title, BOLD, BCYN) + " " + sgr("─" * max(0, w - len(title) - 4), DIM)

def shell_frame(cols):
    w = min(cols - 1, 58); L = []
    t = time.strftime("%H:%M:%S")
    up = read("/proc/uptime").split()[0] or "0"
    try: up = "%dh%02dm" % (int(float(up)) // 3600, (int(float(up)) % 3600) // 60)
    except Exception: pass
    L.append(sgr(" GM5 PLUS · system ", BOLD, WHT, "44") + sgr("  %s  up %s" % (t, up), DIM)); L.append("")
    cu, per = cpu_stats(); gf, gc, gm = gpu_info(); cavg, cmax, pm = cpu_temps()
    onc = sum(1 for _, _, on in per if on); la = " ".join((read("/proc/loadavg").split() + ["?"])[:3])
    cc = GRN if cu < .5 else YEL if cu < .8 else BRED; gcl = GRN if gf < .5 else YEL if gf < .8 else BRED
    L.append(hr("SYSTEM", w))
    L.append("  %s %s %s   %s  %s" % (sgr("CPU ", WHT), abar(cu, 16, cc), sgr("%3d%%" % int(cu*100), BOLD, cc), sgr("yuk %s" % la, DIM), sgr("%d/%dc" % (onc, len(per)), DIM)))
    L.append("  %s %s %s   %s" % (sgr("GPU ", WHT), abar(gf, 16, gcl), sgr("%3d%%" % int(gf*100), BOLD, gcl), sgr("%d/%d MHz" % (gc//1000000, gm//1000000), DIM)))
    L.append("  %s %s   %s" % (sgr("die ", WHT), sgr("avg %.0f max %.0f°C" % (cavg, cmax), tcol(cmax)), sgr("PMIC %s°C" % (("%.0f" % pm) if pm else "?"), DIM)))
    L.append("")
    rr, tr, trx, ttx = net_rate(); lk, lv = wifi_link()
    dtot, dused, dfree = disk_free()
    L.append(hr("NETWORK", w))
    L.append("  %s %s %s  %s" % (sgr("wlan0", WHT), sgr("↓%7s/s" % human(rr), BGRN), sgr("↑%7s/s" % human(tr), BCYN), sgr("Σ↓%s↑%s" % (human(trx), human(ttx)), DIM)))
    if lv is not None:
        sig = max(0.0, min(1.0, (lv + 95) / 55.0)); sc = BRED if sig < .3 else BYEL if sig < .6 else BGRN
        L.append("  %s %s %s" % (sgr("sinyal", WHT), abar(sig, 14, sc), sgr("%.0f dBm" % lv, BOLD, sc)))
    if dtot:
        du = dused / dtot
        L.append("  %s %s %s" % (sgr("/data ", WHT), abar(du, 14, GRN if du < .8 else BYEL), sgr("%s/%s bos %s" % (human(dused), human(dtot), human(dfree)), DIM)))
    L.append("")
    cap, st, hl, bt, vo, cr = battery()
    L.append(hr("BATTERY", w)); bc = BRED if cap < 20 else BYEL if cap < 50 else BGRN
    L.append("  %s %s %s  %s" % (sgr("level", WHT), abar(cap/100.0, 16, bc), sgr("%3d%%" % cap, BOLD, bc), sgr(("⚡"+st) if "harg" in st else st, BGRN if "harg" in st else DIM)))
    L.append("  %s %s  %s  %s  %s" % (sgr("info ", WHT), sgr("%.1f°C" % bt, tcol(bt)), sgr("%.2fV" % vo, BCYN), sgr("%+.0fmA" % cr, BMAG), sgr("%+.2fW" % (vo*cr/1000.0), BMAG))); L.append("")
    sens = merged_sensors()
    L.append(hr("SENSORS (%d)" % len(sens), w))
    if sens:
        for k, v in sens[:8]:
            val, unit = sensor_units(k, v)
            L.append("  %s %s %s" % (sgr(k[:20].ljust(20), WHT), sgr(val, BOLD, BCYN), sgr(unit, DIM)))
        for name, val, unit in derived_rows():
            L.append("  %s %s %s" % (sgr(name[:20].ljust(20), WHT), sgr(val, BOLD, BMAG), sgr(unit, DIM)))
    else: L.append(sgr("  " + SERR[0], DIM))
    if TOUCH["ok"]:
        sl = TOUCH["slots"]
        ts = " ".join("P%d(%d,%d)" % (s, p["x"], p["y"]) for s, p in sorted(sl.items())) or "yok"
        hl = ("  kapak:" + ("kapali" if HALL["closed"] else "acik")) if HALL["ok"] else ""
        L.append("  %s %s%s" % (sgr("touch".ljust(20), WHT), sgr(ts, BGRN), sgr(hl, DIM)))
    return L

def run_shell(once=False):
    if once or not sys.stdout.isatty():
        threading.Thread(target=sensor_reader, args=(200,), daemon=True).start()
        cpu_stats(); gpu_info(); time.sleep(1.2)
        try: cols = os.get_terminal_size().columns
        except Exception: cols = 80
        sys.stdout.write("\n".join(shell_frame(cols)) + "\n"); return
    for t in (sensor_reader, touch_reader, hall_reader):
        threading.Thread(target=t, daemon=True).start()
    import termios, tty, select
    fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
    def restore(*_):
        try: termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception: pass
        try: subprocess.run(["termux-sensor", "-c"], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass
        su("pkill -f 'getevent -l'")
        sys.stdout.write(E + "[?25h" + E + "[?1049l"); sys.stdout.flush(); os._exit(0)
    signal.signal(signal.SIGINT, restore); signal.signal(signal.SIGTERM, restore)
    sys.stdout.write(E + "[?1049h" + E + "[?25l" + E + "[2J"); sys.stdout.flush()
    cpu_stats(); gpu_info()
    try:
        tty.setcbreak(fd); nxt = time.monotonic()
        while True:
            try: cols, rows = os.get_terminal_size()
            except Exception: cols, rows = 80, 24
            body = shell_frame(cols)
            out = [clip(s, cols) for s in body][:rows-1] + [sgr(" f flash | q cikis ", DIM)]
            sys.stdout.write(E + "[H" + "\r\n".join(s + E + "[K" for s in out) + E + "[J"); sys.stdout.flush()
            r, _, _ = select.select([sys.stdin], [], [], max(0.05, nxt + 1 - time.monotonic()))
            if r:
                d = os.read(fd, 8).decode("latin1", "ignore")
                if "q" in d.lower(): restore()
                elif "f" in d: (flash_off() if flash_is_on() else flash_on())
            if time.monotonic() >= nxt + 1: nxt = time.monotonic()
    except Exception: restore()

# ============================== TEXTUAL UI (varsayilan) ==============================
def run_textual(test=False):
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Header, Footer, Static, Button, Label

    def m_temp(t): return "cyan" if t < 38 else "green" if t < 48 else "green3" if t < 58 else "yellow" if t < 68 else "orange1" if t < 76 else "red"
    def mbar(frac, w=18, col="green"):
        frac = max(0.0, min(1.0, frac)); f = int(round(frac * w))
        return f"[{col}]{'█'*f}[/][grey37]{'░'*(w-f)}[/]"

    def md_system():
        cu, per = cpu_stats(); gf, gc, gm = gpu_info(); cavg, cmax, pm = cpu_temps()
        onc = sum(1 for _, _, on in per if on); la = " ".join((read("/proc/loadavg").split() + ["?"])[:3])
        cc = "green" if cu < .5 else "yellow" if cu < .8 else "red"
        gcl = "green" if gf < .5 else "yellow" if gf < .8 else "red"
        return (f"[b cyan]SYSTEM[/]\n"
                f"CPU  {mbar(cu,18,cc)} [b {cc}]{int(cu*100):3d}%[/]  [dim]yuk {la}  {onc}/{len(per)}c[/]\n"
                f"GPU  {mbar(gf,18,gcl)} [b {gcl}]{int(gf*100):3d}%[/]  [dim]{gc//1000000}/{gm//1000000} MHz[/]\n"
                f"die  [{m_temp(cmax)}]avg {cavg:.0f}  max {cmax:.0f}°C[/]   [dim]PMIC {('%.0f'%pm) if pm else '?'}°C[/]")

    def md_net():
        rr, tr, trx, ttx = net_rate(); lk, lv = wifi_link()
        dtot, dused, dfree = disk_free()
        s = f"[b cyan]NETWORK[/]\nwlan0  [green]↓{human(rr)}/s[/]  [cyan]↑{human(tr)}/s[/]  [dim]Σ↓{human(trx)} ↑{human(ttx)}[/]\n"
        if lv is not None:
            sig = max(0.0, min(1.0, (lv + 95) / 55.0)); sc = "red" if sig < .3 else "yellow" if sig < .6 else "green"
            s += f"sinyal {mbar(sig,16,sc)} [b {sc}]{lv:.0f} dBm[/]\n"
        if dtot:
            du = dused / dtot
            s += f"/data  {mbar(du,16,'green' if du<.8 else 'yellow')} [b]{human(dused)}/{human(dtot)}[/] [dim]bos {human(dfree)}[/]"
        return s

    def md_batt():
        cap, st, hl, bt, vo, cr = battery()
        bc = "red" if cap < 20 else "yellow" if cap < 50 else "green"
        chg = f"[green]⚡{st}[/]" if "harg" in st else f"[dim]{st}[/]"
        return (f"[b cyan]BATTERY[/]\nlevel  {mbar(cap/100.0,18,bc)} [b {bc}]{cap}%[/]  {chg}\n"
                f"[{m_temp(bt)}]{bt:.1f}°C[/]  [cyan]{vo:.2f}V[/]  [magenta]{cr:+.0f}mA[/]  [magenta]{vo*cr/1000.0:+.2f}W[/]  [dim]{hl}[/]")

    def md_sensors():
        sens = merged_sensors()
        if not sens: return f"[b cyan]SENSORS[/]\n[dim]{SERR[0]}[/]"
        rows = [f"[b cyan]SENSORS ({len(sens)})[/]"]
        for k, v in sens:
            val, unit = sensor_units(k, v)
            rows.append(f"[white]{k[:22]:22}[/] [b cyan]{val}[/] [dim]{unit}[/]")
        for name, val, unit in derived_rows():
            rows.append(f"[magenta]{name[:22]:22}[/] [b magenta]{val}[/] [dim]{unit}[/]")
        return "\n".join(rows)

    def md_touch():
        sl = TOUCH["slots"]
        s = f"[b cyan]TOUCH ({len(sl)} parmak)[/]\n"
        if not TOUCH["ok"]: return s + f"[dim]{TOUCH['err']}[/]"
        if sl:
            for slot, p in sorted(sl.items()):
                s += f"[green]●[/] P{slot}  [b green]X {p['x']:4d}[/]  [b green]Y {p['y']:4d}[/]\n"
        else:
            lx, ly = TOUCH["last"]; s += f"[grey37]○ son X {lx} Y {ly}[/]\n"
        if HALL["ok"]: s += f"[yellow]kapak: {'kapali' if HALL['closed'] else 'acik'}[/]"
        return s.rstrip()

    class Panel(Static):
        def __init__(self, fn, **kw):
            super().__init__("", **kw); self.fn = fn
        def refresh_data(self):
            try: self.update(self.fn())
            except Exception as e: self.update(f"[red]err: {e}[/]")

    class SystemApp(App):
        CSS = """
        Screen { layout: horizontal; }
        #left { width: 2fr; }
        #right { width: 28; border-left: solid $panel; }
        Panel { border: round $panel; padding: 0 1; margin: 0 0 1 0; }
        .ctrl-title { text-style: bold; color: cyan; padding: 1 0 0 1; }
        Button { width: 100%; margin: 0 1; }
        """
        BINDINGS = [("q", "quit", "Cikis"), ("f", "flash", "Flash"), ("r", "rgb_off", "LED kapat"), ("v", "vib", "Titres")]
        ENABLE_COMMAND_PALETTE = False               # tiklayinca pop_screen crash'ini onler
        NOTIFICATION_TIMEOUT = 2
        def notify(self, message, **kw):             # 2sn goster; ayni anda en fazla 3 (fazlasi atlanir)
            now = time.monotonic()
            tt = getattr(self, "_tt", None)
            if tt is None: tt = self._tt = deque()
            while tt and now - tt[0] > 2.0: tt.popleft()
            if len(tt) >= 3: return
            tt.append(now); kw.setdefault("timeout", 2.0)
            super().notify(message, **kw)
        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with VerticalScroll(id="left"):
                yield Panel(md_system, id="p-sys")
                yield Panel(md_net, id="p-net")
                yield Panel(md_batt, id="p-batt")
                yield Panel(md_sensors, id="p-sens")
                yield Panel(md_touch, id="p-touch")
            with VerticalScroll(id="right"):
                yield Label("KONTROL", classes="ctrl-title")
                yield Button("🔦 Flash", id="flash", variant="warning")
                yield Label("Bildirim LED", classes="ctrl-title")
                yield Button("● Kırmızı", id="led_r", variant="error")
                yield Button("● Yeşil", id="led_g", variant="success")
                yield Button("● Mavi", id="led_b", variant="primary")
                yield Button("LED Kapat", id="led_off")
                yield Label("Diğer", classes="ctrl-title")
                yield Button("📳 Titreşim", id="vibrate")
            yield Footer()
        def on_mount(self):
            for t in (sensor_reader, touch_reader, hall_reader):
                threading.Thread(target=t, daemon=True).start()
            cpu_stats(); gpu_info()
            self.set_interval(2.0, self.tick); self.tick()
        def tick(self):
            for p in self.query(Panel): p.refresh_data()
        def _flash_toggle(self):
            btn = self.query_one("#flash", Button)
            if flash_is_on(): flash_off(); btn.label = "🔦 Flash"; self.notify("Flash kapandı")
            else: flash_on(150); btn.label = "🔦 Flash ✓"; self.notify("Flash açıldı")
        def on_button_pressed(self, ev: "Button.Pressed"):
            bid = ev.button.id
            if bid == "flash": self._flash_toggle(); return
            act = {
                "led_r": (lambda: led_rgb(255, 0, 0), "LED kırmızı"),
                "led_g": (lambda: led_rgb(0, 255, 0), "LED yeşil"),
                "led_b": (lambda: led_rgb(0, 0, 255), "LED mavi"),
                "led_off": (lambda: led_rgb(0, 0, 0), "LED kapandı"),
                "vibrate": (lambda: vibrate(300), "Titreşim"),
            }.get(bid)
            if act: act[0](); self.notify(act[1])
        def action_flash(self): self._flash_toggle()
        def action_rgb_off(self): led_rgb(0, 0, 0); self.notify("LED kapandı")
        def action_vib(self): vibrate(300)
        def on_unmount(self):
            try: subprocess.run(["termux-sensor", "-c"], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass
            su("pkill -f 'getevent -l'")
    if test:
        import asyncio
        async def _t():
            app = SystemApp()
            async with app.run_test() as pilot:
                await pilot.pause(1.6)
                panels = len(app.query(Panel)); btns = [b.id for b in app.query(Button)]
                for bid in ("led_r", "led_g", "led_b", "led_off", "vibrate"):
                    await pilot.click("#" + bid)
                await pilot.pause(0.5)
                shown = len(getattr(app, "_tt", []))
                await pilot.click("#flash"); await pilot.pause(0.2)
                await pilot.press("f"); await pilot.pause(0.2)
                print("MOUNT OK | panels:", panels, "| buttons:", len(btns), "| 5 notify -> gosterilen:", shown, "(<=3 olmali)")
                print("BUTTON IDS:", btns)
        asyncio.run(_t()); return
    SystemApp().run()

# ============================== ENTRY ==============================
def main():
    if "--test-tui" in sys.argv:
        run_textual(test=True); return
    if "--no-tui" in sys.argv or "--once" in sys.argv or not sys.stdout.isatty():
        run_shell(once="--once" in sys.argv); return
    try:
        run_textual()
    except ImportError:
        run_shell()

if __name__ == "__main__":
    main()
