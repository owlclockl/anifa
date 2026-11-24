#!/usr/bin/env python3
"""build_apk.py — сборка подписанного APK «Заметки» из исходников android/.

Требует:
  * aapt2  — /tmp/apkbuild/node_modules/aaptjs3/bin/x64/linux/aapt2 (или $AAPT2)
  * android.jar — /tmp/apkbuild/sdk/android.jar (или $ANDROID_JAR)
  * node + apk_sign_ts — /tmp/apkbuild/node_modules (или $NODE_PATH)
  * python-пакеты: androguard (для проверки DEX; необязательно)

Шаги: classes.dex (make_dex.py) -> aapt2 compile res -> aapt2 link ->
добавление classes.dex в APK -> подпись v1+v2+v3 (sign.cjs) -> проверка.
"""
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
AAPT2 = os.environ.get("AAPT2", "/tmp/apkbuild/node_modules/aaptjs3/bin/x64/linux/aapt2")
ANDROID_JAR = os.environ.get("ANDROID_JAR", "/tmp/apkbuild/sdk/android.jar")
NODE_PATH = os.environ.get("NODE_PATH", "/tmp/apkbuild/node_modules")
WORK = os.environ.get("APK_WORK", "/tmp/apkbuild/work")
OUT_APK = os.path.join(HERE, "zametki-notes.apk")


def run(cmd, **kw):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)


def main():
    os.makedirs(WORK, exist_ok=True)

    # 0. ассет приложения: design/index.html без кнопки скачивания APK
    design_html = os.path.join(HERE, "..", "design", "index.html")
    html = open(design_html, encoding="utf-8").read()
    lines = [ln for ln in html.splitlines(keepends=True) if 'id="apk-link"' not in ln]
    with open(os.path.join(HERE, "assets", "index.html"), "w", encoding="utf-8") as f:
        f.write("".join(lines))

    # 1. classes.dex
    run([sys.executable, os.path.join(HERE, "make_dex.py"),
         os.path.join(WORK, "classes.dex")])

    # 2. ресурсы (иконка)
    flat = os.path.join(WORK, "res.zip")
    run([AAPT2, "compile", "--dir", os.path.join(HERE, "res"), "-o", flat])

    # 3. линковка APK (манифест + ресурсы + assets)
    unsigned = os.path.join(WORK, "unsigned.apk")
    run([AAPT2, "link",
         "-o", unsigned,
         "--manifest", os.path.join(HERE, "AndroidManifest.xml"),
         "-I", ANDROID_JAR,
         "-R", flat,
         "-A", os.path.join(HERE, "assets"),
         "--min-sdk-version", "24",
         "--target-sdk-version", "34",
         "--version-code", "1",
         "--version-name", "1.0"])

    # 4. добавить classes.dex
    stage1 = os.path.join(WORK, "with-dex.apk")
    shutil.copy(unsigned, stage1)
    with zipfile.ZipFile(stage1, "a") as z:
        z.write(os.path.join(WORK, "classes.dex"), "classes.dex")

    # 5. подпись v1+v2+v3
    env = dict(os.environ, NODE_PATH=NODE_PATH)
    run(["node", os.path.join(HERE, "sign.cjs"), stage1, OUT_APK,
         os.path.join(HERE, "keys", "debug-key.pem"),
         os.path.join(HERE, "keys", "debug-cert.pem")], env=env)

    # 6. проверки
    print("\n== aapt2 dump badging ==")
    run([AAPT2, "dump", "badging", OUT_APK])
    with zipfile.ZipFile(OUT_APK) as z:
        names = z.namelist()
        assert "classes.dex" in names, names
        assert "resources.arsc" in names, names
        assert "assets/index.html" in names, names
        assert "res/drawable/ic_launcher.png" in names or any(
            n.startswith("res/") and n.endswith(".png") for n in names), names
        print("zip entries:", names)
    print("\nOK:", OUT_APK, os.path.getsize(OUT_APK), "bytes")


if __name__ == "__main__":
    main()
