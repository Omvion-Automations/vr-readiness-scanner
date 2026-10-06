<h1 align="center">vrscan</h1>

<p align="center"><b>Is your game ready for VR? Find out in 10 seconds.</b><br>
Free, offline, one file. Point it at your game folder or its Steam page.</p>

<p align="center">
<img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8%2B-3b3b4f">
<img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-3b3b4f">
<img alt="MIT" src="https://img.shields.io/badge/license-MIT-3b3b4f">
</p>

```
Portal 2  (steam)
VR readiness: 100 / 100
Strong candidate: the basics a VR port needs are already in place.

  3D world             ########## 25/25  3D
  Camera               ########## 20/20  first-person
  Controller support   ########## 15/15  full
  Genre fit            ########## 10/10  adventure, atmospheric, puzzle
  Comfort              ########## 10/10  no intense-motion tags
  ...
```

## Scan your game

**One line, any terminal** (Windows, Mac, Linux; needs Python 3):

```sh
python -c "import urllib.request as u;exec(u.urlopen('https://raw.githubusercontent.com/Omvion-Automations/vr-readiness-scanner/main/vrscan.py').read())"
```

On Mac and Linux type `python3` instead of `python`; on Windows `py` works too. It asks for your game folder (drag it
into the window) or a Steam store link, and prints the report in colour. Nothing is installed.

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/Omvion-Automations/vr-readiness-scanner/main/vrscan.py -OutFile vrscan.py; py vrscan.py
```

**Mac / Linux:**

```sh
curl -sO https://raw.githubusercontent.com/Omvion-Automations/vr-readiness-scanner/main/vrscan.py && python3 vrscan.py
```

**No terminal?** Download this repo (green **Code** button, **Download ZIP**), unzip it, and drag your game folder onto
`vrscan.bat` (Windows). No Python yet? Get it from [python.org](https://www.python.org/downloads/) or run
`winget install Python.Python.3.12`.

Once you have the file, you can pass the game straight away:

```sh
python3 vrscan.py ~/Games/MyGame                                   # a built game or a Unity / Unreal / Godot project
python3 vrscan.py https://store.steampowered.com/app/620/Portal_2/ # any game on Steam
python3 vrscan.py 620 --json                                       # JSON, for scripts
```

Prefer a command? `pipx install git+https://github.com/Omvion-Automations/vr-readiness-scanner`, then `vrscan`.

## What the score means

| Score | Verdict |
|---|---|
| 75-100 | **Strong candidate.** The basics a VR port needs are already in place. |
| 55-74 | **Good candidate.** Portable, with a few areas that need real VR design work. |
| 35-54 | **Possible, with effort.** Expect significant camera, UI or control rework. |
| 0-34 | **Hard port.** The game's structure fights VR; a VR spin-off may suit it better. |

Every point is explained in the report, so you can see exactly why.

## Private by design

Folder scans run entirely on your machine. vrscan looks at file names and searches a few engine files for version
strings, to identify the engine, its version and what is already installed. It never uploads anything. Steam scans only read the game's public
store page.

<details>
<summary><b>What it checks</b></summary>

**Game folder** (a build or a project):

| Check | Points | What it looks for |
|---|---|---|
| Engine | 20 | Unity, Unreal or Godot, build or project |
| Engine version | 15 | Unity 2020.3+, UE 4.26+/5, Godot 4 ship OpenXR support |
| Existing XR pieces | 15 | OpenXR loader, OVRPlugin, OpenVR, Unity XR packages, engine OpenXR plugins |
| Graphics API | 10 | DirectX 11/12 or Vulkan |
| Render pipeline | 10 | Unity URP / Built-in / HDRP (cost per eye, standalone headsets) |
| Input system | 10 | action-based input (Input System, Enhanced Input, Rewired) maps onto VR controllers |
| 3D content | 20 | 3D model files in a project (builds pack assets away, so this is partial for builds) |

**Steam page** (public store data: categories, genres, user tags, review summary):

| Check | Points | What it looks for |
|---|---|---|
| 3D world | 25 | 3D, first-person, third-person, open world vs 2D, pixel, side-scroller |
| Camera | 20 | first-person beats third-person beats top-down |
| Controller support | 15 | full or partial gamepad support |
| Genre fit | 10 | exploration, puzzle, sim, horror, racing, flight, survival |
| Comfort | 10 | fast-paced, platformer, arena or rhythm tags flag motion-sickness risk |
| Single-player | 10 | single-player content ports first |
| Audience | 10 | review count and share positive |

The score is the share of points earned. A clearly 2D game is capped at 30: VR is about standing inside a world.

</details>

<details>
<summary><b>Limits</b></summary>

- It is a quick estimate from files and public store data. It cannot see your code, shaders, UI layout or camera
  scripting, which is where most real porting work lives.
- Builds hide a lot: IL2CPP Unity builds compile code away, and packed assets hide 3D vs 2D.
- Steam tags are written by players and can be wrong.

Treat the result as a conversation starter, not a verdict.

</details>

## Want the full picture?

vrscan gives a quick read. For a detailed VR readiness report on your game, free, visit [omvion.org](https://omvion.org).

## Contributing

Issues and pull requests are welcome, especially new detection signals with a test case in `tests/`.
Run the tests: `python3 -m unittest discover -s tests`.

MIT licensed. Made by [OMVION](https://omvion.org).
