#!/usr/bin/env python3
"""vrscan: a quick, honest VR-readiness estimate for a flat (non-VR) game.

    vrscan <folder>             a built game folder, or a Unity / Unreal / Godot project folder
    vrscan steam <appid|url>    a game on Steam, from its public store data
    add --json for machine-readable output

Every check is shown with its points so you can see exactly why a game scored what it did.
It is a heuristic from files and store data, not a guarantee: a real port depends on code you can't see from outside.
Python 3.8+, standard library only.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

__version__ = "0.1.0"
UA = "vrscan/%s (+https://github.com/Omvion-Automations/vr-readiness-scanner)" % __version__
MAX_READ = 64 * 1024 * 1024   # never read more than this much of any single file


class Check:
    def __init__(self, name, max_points):
        self.name, self.max, self.points, self.found, self.note = name, max_points, 0, "", ""

    def set(self, points, found, note):
        self.points, self.found, self.note = max(0, min(self.max, points)), found, note
        return self

    def as_dict(self):
        return {"check": self.name, "points": self.points, "max": self.max, "found": self.found, "note": self.note}


def verdict(score):
    if score >= 75:
        return "Strong candidate: the basics a VR port needs are already in place."
    if score >= 55:
        return "Good candidate: portable, with a few areas that need real VR design work."
    if score >= 35:
        return "Possible, with effort: expect significant camera, UI or control rework."
    return "Hard port: the game's structure fights VR; a VR spin-off may suit it better than a port."


FLAT_CAP = 30   # a confirmed-2D game can't look like a good VR port just because everything else is polished


def report(subject, mode, checks, extra=None, flat=False):
    score = sum(c.points for c in checks)
    total = sum(c.max for c in checks)
    score = round(100 * score / total) if total else 0
    if flat:
        score = min(score, FLAT_CAP)
    out = {"subject": subject, "mode": mode, "score": score, "verdict": verdict(score), "checks": [c.as_dict() for c in checks],
           "disclaimer": "Heuristic estimate from public or file-level signals, not a guarantee."}
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------- folder mode

def walk(root, limit=60000):
    """(relative path, size) for files under root, capped so huge folders stay fast."""
    n = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in (".git", "Library", "Temp", "obj", "Intermediate", "DerivedDataCache", "node_modules", ".godot")]
        for f in files:
            p = os.path.join(d, f)
            try:
                yield os.path.relpath(p, root).replace("\\", "/"), os.path.getsize(p)
            except OSError:
                continue
            n += 1
            if n >= limit:
                return


def grep_bytes(path, pattern, limit=MAX_READ):
    """First match of a bytes regex inside a file (chunked, bounded)."""
    rx = re.compile(pattern)
    try:
        with open(path, "rb") as f:
            tail, read = b"", 0
            while read < limit:
                chunk = f.read(4 * 1024 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                m = rx.search(tail + chunk)
                if m:
                    return m.group(1) if m.groups() else m.group(0)
                tail = chunk[-256:]
    except OSError:
        pass
    return None


def read_text(path, limit=2_000_000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def detect(root):
    """Collect raw facts about a game or project folder."""
    files = list(walk(root))
    names = [p for p, _ in files]
    low = [p.lower() for p in names]
    base = {os.path.basename(p) for p in low}
    facts = {"engine": None, "version": None, "kind": None, "pipeline": None, "graphics": [], "xr": [], "input": None,
             "assets3d": 0, "assets2d": 0, "il2cpp": False}

    def has(*parts):
        return any(any(part in p for part in parts) for p in low)

    # --- engine + version
    if "projectsettings/projectversion.txt" in low:
        facts.update(engine="Unity", kind="project")
        m = re.search(r"m_EditorVersion:\s*(\S+)", read_text(os.path.join(root, names[low.index("projectsettings/projectversion.txt")])))
        facts["version"] = m.group(1) if m else None
    elif "unityplayer.dll" in base or any(p.endswith("_data/globalgamemanagers") for p in low) or any(p.endswith("_data/data.unity3d") for p in low):
        facts.update(engine="Unity", kind="build")
        ggm = next((names[i] for i, p in enumerate(low) if p.endswith("_data/globalgamemanagers")), None)
        if ggm:
            v = grep_bytes(os.path.join(root, ggm), rb"(20\d\d\.\d+\.\d+[abfp]\d+|[56]\.\d+\.\d+[abfp]\d+)", 4096)
            facts["version"] = v.decode() if v else None
        facts["il2cpp"] = "gameassembly.dll" in base or "libil2cpp.so" in base
    elif any(p.endswith(".uproject") for p in low):
        facts.update(engine="Unreal", kind="project")
        up = names[next(i for i, p in enumerate(low) if p.endswith(".uproject"))]
        try:
            facts["version"] = json.loads(read_text(os.path.join(root, up))).get("EngineAssociation") or None
        except ValueError:
            pass
    elif any(p.endswith(".pak") for p in low) and (has("/binaries/win64/") or has("engine/")):
        facts.update(engine="Unreal", kind="build")
        exes = sorted((s, names[i]) for i, (p, s) in enumerate(zip(low, (s for _, s in files))) if p.endswith(".exe") and "/binaries/win64/" in p)
        if exes:
            v = grep_bytes(os.path.join(root, exes[-1][1]), rb"\+\+UE([45])\+Release-(\d\.\d+)")
            facts["version"] = v.decode().split("Release-")[-1] if v else None
            if v is None:
                m = grep_bytes(os.path.join(root, exes[-1][1]), rb"UE([45])\.\d+")
                facts["version"] = m.decode().replace("UE", "") if m else None
    elif "project.godot" in base:
        facts.update(engine="Godot", kind="project")
        m = re.search(r'config/features=PackedStringArray\("(\d\.\d+)', read_text(os.path.join(root, names[low.index(next(p for p in low if p.endswith("project.godot")))])))
        facts["version"] = m.group(1) if m else None
    elif any(p.endswith(".pck") for p in low):
        facts.update(engine="Godot", kind="build")

    # --- render pipeline (Unity)
    if facts["engine"] == "Unity":
        manifest = next((names[i] for i, p in enumerate(low) if p == "packages/manifest.json"), None)
        if manifest:
            mt = read_text(os.path.join(root, manifest))
            facts["pipeline"] = "HDRP" if "render-pipelines.high-definition" in mt else "URP" if "render-pipelines.universal" in mt else "Built-in"
            facts["input"] = "Input System" if "com.unity.inputsystem" in mt else None
            facts["xr"] += [x for x, key in (("Unity OpenXR", "com.unity.xr.openxr"), ("XR Plugin Management", "com.unity.xr.management"),
                                             ("Oculus XR", "com.unity.xr.oculus"), ("XR Interaction Toolkit", "com.unity.xr.interaction.toolkit")) if key in mt]
        else:
            if has("unity.renderpipelines.high-definition"):
                facts["pipeline"] = "HDRP"
            elif has("unity.renderpipelines.universal"):
                facts["pipeline"] = "URP"
            elif not facts["il2cpp"] and has("_data/managed/"):
                facts["pipeline"] = "Built-in"
            if has("unity.xr.openxr"):
                facts["xr"].append("Unity OpenXR")
            if has("unity.xr.management"):
                facts["xr"].append("XR Plugin Management")
        if facts["input"] is None:
            facts["input"] = "Input System" if has("unity.inputsystem.dll") else "Rewired" if has("rewired_core.dll", "/rewired/") else ("Legacy Input Manager" if has("_data/managed/", "projectsettings/inputmanager.asset") else None)
        if facts["input"] is None and has("/rewired/"):
            facts["input"] = "Rewired"

    if facts["engine"] == "Unreal" and facts["kind"] == "project":
        ini = read_text(os.path.join(root, "Config", "DefaultEngine.ini")) + read_text(os.path.join(root, next((n for n in names if n.lower().endswith(".uproject")), "")))
        if re.search(r'"Name"\s*:\s*"OpenXR"[^}]*"Enabled"\s*:\s*true', ini):
            facts["xr"].append("Unreal OpenXR plugin")
        facts["input"] = "Enhanced Input" if "EnhancedInput" in ini else "Legacy input" if ini else None
    if facts["engine"] == "Godot" and facts["kind"] == "project":
        gt = read_text(os.path.join(root, names[low.index(next(p for p in low if p.endswith("project.godot")))]))
        if re.search(r"xr/openxr/enabled\s*=\s*true", gt):
            facts["xr"].append("Godot OpenXR")

    # --- runtime libs any engine ships
    for lib, label in (("openxr_loader", "OpenXR loader"), ("ovrplugin", "Oculus OVRPlugin"), ("openvr_api", "OpenVR / SteamVR")):
        if has(lib) and label not in facts["xr"]:
            facts["xr"].append(label)
    facts["graphics"] = [g for g, keys in (("DirectX 12", ("d3d12",)), ("Vulkan", ("vulkan", "vk_", "libvulkan")), ("DirectX 11", ("d3d11",)))
                         if any(k in b for k in keys for b in base)]
    if facts["engine"] == "Unity" and not facts["graphics"] and facts["kind"] == "build":
        facts["graphics"] = ["DirectX 11 (Unity default)"]
    if facts["engine"] == "Unreal" and not facts["graphics"]:
        facts["graphics"] = ["DirectX 11/12 (Unreal default)"]

    # --- 3D vs 2D content signals (projects only: builds pack assets away)
    for p in low:
        ext = os.path.splitext(p)[1]
        if ext in (".fbx", ".obj", ".blend", ".gltf", ".glb", ".dae"):
            facts["assets3d"] += 1
        if ext in (".png", ".psd", ".aseprite") and ("sprite" in p or "tiles" in p or "pixel" in p):
            facts["assets2d"] += 1
    if facts["engine"] == "Unreal":
        facts["assets3d"] = max(facts["assets3d"], 1)   # Unreal games are 3D by default
    return facts


def ver_tuple(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in nums[:2]) if nums else ()


def score_folder(root):
    f = detect(root)
    c = []
    e = Check("Engine", 20)
    if f["engine"]:
        e.set({"Unity": 20, "Unreal": 20, "Godot": 15}[f["engine"]], "%s %s%s" % (f["engine"], f["kind"], (" " + f["version"]) if f["version"] else ""),
              "Mainstream engines have mature VR toolchains (OpenXR) and known porting paths.")
    else:
        e.set(0, "not recognised", "Custom or unknown engine: VR support has to be built from the renderer up.")
    c.append(e)

    v, vt = Check("Engine version", 15), ver_tuple(f["version"])
    if f["engine"] == "Unity" and vt:
        pts = 15 if vt >= (2020, 3) else 10 if vt >= (2019, 4) else 4
        v.set(pts, f["version"], "Unity 2020.3+ supports OpenXR through XR Plugin Management; older versions need an engine upgrade first." if pts < 15 else
              "Recent enough for Unity's OpenXR plugin without an engine upgrade.")
    elif f["engine"] == "Unreal" and vt:
        pts = 15 if vt >= (4, 26) else 8
        v.set(pts, f["version"], "UE 4.26+ and UE5 ship OpenXR support in the engine." if pts == 15 else "Older Unreal: OpenXR needs an engine upgrade or legacy plugins.")
    elif f["engine"] == "Godot" and vt:
        v.set(15 if vt >= (4, 0) else 8, f["version"], "Godot 4 has OpenXR built in." if vt >= (4, 0) else "Godot 3 needs the OpenXR plugin.")
    else:
        v.set(5 if f["engine"] else 0, "unknown", "Version not detectable from these files.")
    c.append(v)

    x = Check("Existing XR pieces", 15)
    x.set(15 if f["xr"] else 0, ", ".join(f["xr"]) or "none", "XR libraries already ship with the game: some VR plumbing exists." if f["xr"] else
          "No XR libraries found. Normal for a flat game; the VR runtime gets added during the port.")
    c.append(x)

    g = Check("Graphics API", 10)
    good = [a for a in f["graphics"] if "DirectX 11" in a or "Vulkan" in a or "DirectX 12" in a]
    g.set(10 if good else 3, ", ".join(f["graphics"]) or "unknown", "DirectX 11/12 and Vulkan are what PC VR runtimes expect." if good else
          "Couldn't confirm a VR-friendly graphics API.")
    c.append(g)

    r = Check("Render pipeline", 10)
    if f["engine"] == "Unity" and f["pipeline"]:
        r.set({"URP": 10, "Built-in": 8, "HDRP": 5}[f["pipeline"]], f["pipeline"], {"URP": "URP supports single-pass stereo and runs well on standalone headsets.",
              "Built-in": "Built-in pipeline does VR fine on PC; standalone headsets will want optimisation.",
              "HDRP": "HDRP is PC-only in VR and expensive per eye: expect heavy optimisation."}[f["pipeline"]])
    elif f["engine"] in ("Unreal", "Godot"):
        r.set(7, "engine default", "Forward/mobile renderer paths are usually needed for good VR performance.")
    else:
        r.set(0 if not f["engine"] else 4, "unknown", "Pipeline not detectable." + (" IL2CPP build: managed assemblies are compiled away." if f["il2cpp"] else ""))
    c.append(r)

    i = Check("Input system", 10)
    ip = f["input"]
    i.set({"Input System": 10, "Enhanced Input": 10, "Rewired": 8}.get(ip, 5 if ip else 3), ip or "unknown",
          "Action-based input maps cleanly onto VR controllers." if ip in ("Input System", "Enhanced Input", "Rewired") else
          "Direct key/axis input: controls will need an action layer for VR controllers.")
    c.append(i)

    d = Check("3D content", 20)
    if f["assets3d"] or f["engine"] == "Unreal":
        d.set(20 if f["assets2d"] <= f["assets3d"] else 10, "%d 3D model files, %d sprite-like files" % (f["assets3d"], f["assets2d"]) if f["kind"] == "project" else "3D engine content",
              "A 3D world is the single biggest factor: you can stand inside it.")
    elif f["kind"] == "build":
        d.set(10, "packed in build", "Builds pack their assets, so 3D vs 2D can't be confirmed from files. Use `vrscan steam` for store tags.")
    else:
        d.set(0, "no 3D models found", "Looks 2D: VR suits 2D games poorly unless they're re-imagined.")
    c.append(d)
    return report(os.path.abspath(root), "folder", c, {"facts": f}, flat=d.found == "no 3D models found")


# ---------------------------------------------------------------- steam mode

def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cookie": "birthtime=0; wants_mature_content=1; lastagecheckage=1-0-1990"})
    for n in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and n < tries - 1:
                time.sleep(5 * (n + 1))   # Steam rate limit: back off and retry
                continue
            raise
        except urllib.error.URLError:
            if n < tries - 1:
                time.sleep(2)
                continue
            raise


def appid_of(s):
    m = re.search(r"/app/(\d+)", s) or re.fullmatch(r"\s*(\d+)\s*", s)
    if not m:
        raise SystemExit("Give a Steam app id (e.g. 620) or a store URL (https://store.steampowered.com/app/620/).")
    return m.group(1)


def steam_data(appid):
    d = json.loads(fetch("https://store.steampowered.com/api/appdetails?appids=%s&l=english" % appid)).get(str(appid), {})
    if not d.get("success"):
        raise SystemExit("Steam has no public store data for app %s." % appid)
    data = d["data"]
    try:
        page = fetch("https://store.steampowered.com/app/%s/?l=english" % appid)
        tags = [t.strip() for t in re.findall(r'class="app_tag"[^>]*>\s*([^<]+?)\s*<', page)][:20]
    except Exception:
        tags = []
    try:
        rv = json.loads(fetch("https://store.steampowered.com/appreviews/%s?json=1&language=all&purchase_type=all&num_per_page=0" % appid)).get("query_summary", {})
    except Exception:
        rv = {}
    return data, tags, rv


FIRST, THIRD = {"first-person", "fps", "immersive sim"}, {"third person", "third-person shooter"}
TOPDOWN = {"top-down", "isometric", "top-down shooter", "rts"}
FLAT = {"2d", "pixel graphics", "side scroller", "2d platformer", "platformer", "metroidvania", "visual novel", "card game", "text-based", "bullet hell"}
CALM = {"exploration", "puzzle", "walking simulator", "simulation", "horror", "atmospheric", "adventure", "racing", "flight", "relaxing", "building", "sandbox", "survival"}
INTENSE = {"fast-paced", "precision platformer", "bullet hell", "arena shooter", "fighting", "rhythm", "competitive", "pvp", "moba"}


def score_steam(raw):
    appid = appid_of(raw)
    data, tags, rv = steam_data(appid)
    t = {x.lower() for x in tags}
    cats = {c.get("description", "").lower() for c in data.get("categories", [])}
    genres = {g.get("description", "").lower() for g in data.get("genres", [])}
    words = t | genres
    c = []

    w = Check("3D world", 25)
    if "3d" in t or words & (FIRST | THIRD | {"open world", "3d platformer"}):
        w.set(25, "3D", "A 3D world is the single biggest factor: you can stand inside it.")
    elif words & FLAT:
        w.set(0, "2D", "2D games don't translate to VR without being re-imagined.")
    else:
        w.set(12, "unclear from tags", "Store tags don't say 3D or 2D clearly.")
    c.append(w)

    p = Check("Camera", 20)
    if words & FIRST:
        p.set(20, "first-person", "First-person maps directly onto a headset view.")
    elif words & THIRD:
        p.set(13, "third-person", "Third-person works in VR (over-the-shoulder or tabletop) but needs a camera decision.")
    elif words & TOPDOWN:
        p.set(8, "top-down / isometric", "Top-down suits a 'diorama' VR view; good for some genres, a redesign for others.")
    else:
        p.set(5 if w.points else 0, "unknown", "Camera style not clear from store tags.")
    c.append(p)

    k = Check("Controller support", 15)
    if "full controller support" in cats:
        k.set(15, "full", "Already plays on a gamepad, so every action has an input mapping VR controllers can take over.")
    elif "partial controller support" in cats:
        k.set(8, "partial", "Some actions are mouse/keyboard only and will need VR interactions designed.")
    else:
        k.set(2, "keyboard & mouse", "Mouse-driven controls need the most rework for motion controllers.")
    c.append(k)

    f = Check("Genre fit", 10)
    fit = sorted(words & CALM)
    f.set(10 if len(fit) >= 2 else 6 if fit else 3, ", ".join(fit) or "none of the classic VR genres", "Exploration, puzzle, sim, horror and racing are proven VR genres.")
    c.append(f)

    m = Check("Comfort", 10)
    hot = sorted(words & INTENSE)
    m.set(3 if hot else 10, ", ".join(hot) or "no intense-motion tags", "Fast, twitchy movement is the main motion-sickness risk; it needs comfort options." if hot else
          "Nothing in the tags points to hard comfort problems.")
    c.append(m)

    s = Check("Single-player", 10)
    sp = "single-player" in cats
    mp_only = not sp and cats & {"multi-player", "online pvp", "mmo"}
    s.set(10 if sp else 2 if mp_only else 5, "yes" if sp else "multiplayer-focused" if mp_only else "unknown",
          "Single-player content is the easiest to bring to VR first." if sp else "Online multiplayer adds cross-play and balance questions to a VR port.")
    c.append(s)

    d = Check("Audience", 10)
    total, pos = rv.get("total_reviews", 0) or 0, rv.get("total_positive", 0) or 0
    share = pos / total if total else 0
    d.set(10 if total >= 500 and share >= 0.8 else 6 if total >= 100 and share >= 0.7 else 3 if total else 0,
          "%d reviews, %d%% positive" % (total, round(share * 100)) if total else "no reviews", "A well-loved game has players who'd buy it again in VR.")
    c.append(d)

    vr = sorted({c.get("description", "") for c in data.get("categories", []) if c.get("id") in (31, 53, 54) or "vr" in c.get("description", "").lower()})
    out = report(data.get("name", appid), "steam", c, {"appid": int(appid), "url": "https://store.steampowered.com/app/%s/" % appid, "tags": tags,
                                                       "already_vr": bool(vr), "vr_categories": vr}, flat=w.found == "2D")
    if vr:
        out["verdict"] = "Already supports VR on Steam (%s). %s" % (", ".join(vr), out["verdict"])
    return out


# ---------------------------------------------------------------- output

def bar(points, mx, width=10):
    n = round(width * points / mx) if mx else 0
    return "#" * n + "." * (width - n)


def print_report(r):
    print("\n%s  (%s)" % (r["subject"], r["mode"]))
    print("VR readiness: %d / 100\n%s\n" % (r["score"], r["verdict"]))
    for c in r["checks"]:
        print("  %-20s %s %2d/%-2d  %s" % (c["check"], bar(c["points"], c["max"]), c["points"], c["max"], c["found"]))
        print("  %-20s %s" % ("", c["note"]))
    print("\n%s\n" % r["disclaimer"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vrscan", description="Quick, honest VR-readiness estimate for a flat game.")
    ap.add_argument("target", nargs="+", help="a folder, or: steam <appid|store url>")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--version", action="version", version="vrscan " + __version__)
    a = ap.parse_args(argv)
    if a.target[0] == "steam":
        if len(a.target) < 2:
            ap.error("steam needs an app id or store URL")
        r = score_steam(a.target[1])
    else:
        if not os.path.isdir(a.target[0]):
            ap.error("not a folder: %s" % a.target[0])
        r = score_folder(a.target[0])
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print_report(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
