# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import copy_metadata, collect_submodules

datas = [("../combuddy/web", "combuddy/web"),
         ("../combuddy/demo/previews", "combuddy/demo/previews")]
datas += copy_metadata("combuddy")        # ship .dist-info so importlib.metadata.version works

hiddenimports = collect_submodules("uvicorn")

a = Analysis(["desktop_entry.py"], pathex=[".."], datas=datas,
             hiddenimports=hiddenimports, noarchive=False)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="combuddy",
              console=False, icon="icons/combuddy.icns")
    coll = COLLECT(exe, a.binaries, a.datas, name="combuddy")
    app = BUNDLE(coll, name="combuddy.app", icon="icons/combuddy.icns",
                 bundle_identifier="io.github.peilinok.combuddy",
                 info_plist={"NSHighResolutionCapable": True})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="combuddy",
              console=False, onefile=True, icon="icons/combuddy.ico")
