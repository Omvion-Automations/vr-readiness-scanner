import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vrscan


def make(root, files):
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(content if isinstance(content, bytes) else content.encode())


class FolderMode(unittest.TestCase):
    def test_unity_project_urp(self):
        with tempfile.TemporaryDirectory() as d:
            make(d, {"ProjectSettings/ProjectVersion.txt": "m_EditorVersion: 2022.3.10f1\n",
                     "Packages/manifest.json": json.dumps({"dependencies": {"com.unity.render-pipelines.universal": "14.0.8", "com.unity.inputsystem": "1.7.0"}}),
                     "Assets/Models/hero.fbx": "x", "Assets/Models/level.fbx": "x"})
            r = vrscan.score_folder(d)
            f = r["facts"]
            self.assertEqual((f["engine"], f["kind"], f["version"], f["pipeline"], f["input"]), ("Unity", "project", "2022.3.10f1", "URP", "Input System"))
            self.assertGreaterEqual(r["score"], 70)

    def test_unity_build_with_openxr(self):
        with tempfile.TemporaryDirectory() as d:
            make(d, {"UnityPlayer.dll": "x", "Game_Data/globalgamemanagers": b"\x00\x00" + b"2021.3.5f1" + b"\x00" * 50,
                     "Game_Data/Managed/Unity.InputSystem.dll": "x", "Game_Data/Plugins/x86_64/openxr_loader.dll": "x", "d3d11.dll": "x"})
            f = vrscan.score_folder(d)["facts"]
            self.assertEqual((f["engine"], f["kind"], f["version"]), ("Unity", "build", "2021.3.5f1"))
            self.assertIn("OpenXR loader", f["xr"])
            self.assertEqual(f["input"], "Input System")

    def test_unreal_project(self):
        with tempfile.TemporaryDirectory() as d:
            make(d, {"MyGame.uproject": json.dumps({"EngineAssociation": "5.3", "Plugins": [{"Name": "OpenXR", "Enabled": True}]}),
                     "Config/DefaultEngine.ini": "[/Script/EnhancedInput.EnhancedInputDeveloperSettings]\n"})
            f = vrscan.score_folder(d)["facts"]
            self.assertEqual((f["engine"], f["version"], f["input"]), ("Unreal", "5.3", "Enhanced Input"))
            self.assertIn("Unreal OpenXR plugin", f["xr"])

    def test_godot_project(self):
        with tempfile.TemporaryDirectory() as d:
            make(d, {"project.godot": 'config/features=PackedStringArray("4.2", "Forward Plus")\n'})
            f = vrscan.score_folder(d)["facts"]
            self.assertEqual((f["engine"], f["version"]), ("Godot", "4.2"))

    def test_unknown_folder_scores_low(self):
        with tempfile.TemporaryDirectory() as d:
            make(d, {"readme.txt": "hello"})
            self.assertLess(vrscan.score_folder(d)["score"], 20)


class Basics(unittest.TestCase):
    def test_appid_parsing(self):
        self.assertEqual(vrscan.appid_of("620"), "620")
        self.assertEqual(vrscan.appid_of("https://store.steampowered.com/app/620/Portal_2/"), "620")
        with self.assertRaises(SystemExit):
            vrscan.appid_of("portal")

    def test_score_is_percent_of_max(self):
        c = [vrscan.Check("a", 10).set(5, "", ""), vrscan.Check("b", 30).set(30, "", "")]
        self.assertEqual(vrscan.report("x", "t", c)["score"], 88)


class SteamMode(unittest.TestCase):
    def fake(self, tags, genres=()):
        data = {"name": "Test", "genres": [{"description": g} for g in genres], "categories": [{"description": "Single-player"}]}
        orig = vrscan.steam_data
        vrscan.steam_data = lambda appid: (data, tags, {"total_reviews": 1000, "total_positive": 950})
        try:
            return {c["check"]: c for c in vrscan.score_steam("1")["checks"]}
        finally:
            vrscan.steam_data = orig

    def test_pixel_open_world_is_2d(self):   # Stardew Valley regression: "Open World" must not beat "2D" / "Pixel Graphics"
        self.assertEqual(self.fake(["Farming Sim", "Pixel Graphics", "Open World", "2D"])["3D world"]["points"], 0)

    def test_portal2_platformer_is_3d(self):   # "Platformer" alone is not a 2D signal
        tags = ["Singleplayer", "Platformer", "Puzzle", "First-Person", "Puzzle Platformer", "3D Platformer", "FPS"]
        self.assertEqual(self.fake(tags)["3D world"]["points"], 25)

    def test_first_person_3d(self):
        self.assertEqual(self.fake(["FPS", "3D", "Atmospheric"])["3D world"]["points"], 25)


if __name__ == "__main__":
    unittest.main()
