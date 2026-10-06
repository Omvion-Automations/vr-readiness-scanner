# vrscan

A quick, honest VR-readiness estimate for a flat (non-VR) game. Point it at a game folder, a Unity / Unreal / Godot
project, or a Steam page, and it tells you how hard a VR port is likely to be, with every point explained.

```
$ python3 vrscan.py steam 620

Portal 2  (steam)
VR readiness: 100 / 100
Strong candidate: the basics a VR port needs are already in place.

  3D world             ########## 25/25  3D
  Camera               ########## 20/20  first-person
  Controller support   ########## 15/15  full
  ...
```

## Run it

No dependencies, Python 3.8+.

```
python3 vrscan.py <folder>               # a built game, or a Unity / Unreal / Godot project
python3 vrscan.py steam <appid|url>      # a game on Steam
python3 vrscan.py steam 620 --json       # JSON for scripts
```

Or install the `vrscan` command: `pipx install git+https://github.com/Omvion-Automations/vr-readiness-scanner`
(or `pip install .` from a clone).

## What it checks

**Folder mode** (a build or a project):

| Check | Points | What it looks for |
|---|---|---|
| Engine | 20 | Unity, Unreal or Godot, build or project |
| Engine version | 15 | Unity 2020.3+, UE 4.26+/5, Godot 4 have OpenXR support in the engine |
| Existing XR pieces | 15 | OpenXR loader, OVRPlugin, OpenVR, Unity XR packages, engine OpenXR plugins |
| Graphics API | 10 | DirectX 11/12 or Vulkan |
| Render pipeline | 10 | Unity URP / Built-in / HDRP (cost per eye, standalone headsets) |
| Input system | 10 | Action-based input (Input System, Enhanced Input, Rewired) maps onto VR controllers |
| 3D content | 20 | 3D model files in a project (builds pack assets away, so this is partial for builds) |

**Steam mode** (public store data: categories, genres, user tags, review summary):

| Check | Points | What it looks for |
|---|---|---|
| 3D world | 25 | 3D / first-person / third-person / open world tags vs 2D, pixel, side-scroller |
| Camera | 20 | first-person > third-person > top-down |
| Controller support | 15 | full / partial gamepad support |
| Genre fit | 10 | exploration, puzzle, sim, horror, racing, flight, survival... |
| Comfort | 10 | fast-paced, platformer, arena or rhythm tags flag motion-sickness risk |
| Single-player | 10 | single-player content ports first |
| Audience | 10 | review count and share positive |

The score is the share of points earned, out of 100. A game that is clearly 2D is capped at 30: VR is about standing
inside a world, and polish elsewhere doesn't change that.

## Limits (read these)

- It is a heuristic from files and public store data. It cannot see your code, shaders, UI layout or how your camera is
  scripted, which is where most real porting work lives.
- Builds hide a lot: IL2CPP Unity builds compile managed code away, and packed assets hide 3D vs 2D.
- Steam tags are written by players and can be wrong.
- Treat the result as a conversation starter, not a verdict.

## Contributing

Issues and pull requests welcome, especially new detection signals with a test case in `tests/`.
Run the tests with `python3 -m unittest discover -s tests`.

## License

MIT. Made by [OMVION](https://omvion.org).
