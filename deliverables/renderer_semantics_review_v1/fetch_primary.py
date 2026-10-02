"""Fetch a small explicit primary-source set; no repository clone or scanning."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import urllib.request

HERE = Path(__file__).resolve().parent
OUT = HERE / "sources"
OUT.mkdir(exist_ok=True)
LOG = HERE / "FETCH_LOG.json"
records = json.loads(LOG.read_text()) if LOG.exists() else []


def fetch(name, url, revision):
    record = {"id": name, "url": url, "revision": revision, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "HybridGuard-local-source-review"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Source exceeds bounded retrieval size")
        text = data.decode("utf-8")
        path = OUT / (name + ".txt")
        path.write_text(text)
        record.update(status="RETRIEVED", local_path=str(path.relative_to(HERE)), lines=len(text.splitlines()))
        print(name, "RETRIEVED", len(data), flush=True)
    except Exception as error:
        record.update(status="FAILED", error=str(error))
        text = None
        print(name, "FAILED", str(error), flush=True)
    records[:] = [r for r in records if r["id"] != name]
    records.append(record)
    LOG.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    return text


if __name__ == "__main__":
    version = "134.0.6998.135"
    chromium = "https://raw.githubusercontent.com/chromium/chromium/" + version + "/"
    deps = fetch("chromium134_deps", chromium + "DEPS", version)
    if deps:
        match = re.search(r"'angle_revision':\s*'([0-9a-f]+)'", deps)
        if not match:
            raise RuntimeError("ANGLE revision not found in Chromium DEPS")
        revision = match.group(1)
        base = "https://raw.githubusercontent.com/google/angle/" + revision + "/"
        for name, path in (
            ("angle_context", "src/libANGLE/Context.cpp"),
            ("angle_display_gl", "src/libANGLE/renderer/gl/DisplayGL.cpp"),
            ("angle_display_gl_tests", "src/libANGLE/renderer/gl/DisplayGL_unittest.cpp"),
            ("angle_renderer_d3d11", "src/libANGLE/renderer/d3d/d3d11/Renderer11.cpp"),
            ("angle_readme", "README.md"),
            ("angle_android_setup", "doc/DevSetupAndroid.md"),
        ):
            fetch(name, base + path, revision)
    fetch("chromium134_webgl", chromium + "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc", version)
    fetch("khronos_debug_renderer", "https://registry.khronos.org/webgl/extensions/WEBGL_debug_renderer_info/", "Revision 8; specification date 2014-07-15")
    fetch("khronos_gles_getstring", "https://registry.khronos.org/OpenGL-Refpages/es2.0/xhtml/glGetString.xml", "OpenGL ES 2.0 reference; live page")
    fetch("android_emulator_settings", "https://developer.android.com/studio/run/devsite-two-way-merge-new", "Live documentation; includes legacy Windows ANGLE option")
    fetch("android_emulator_acceleration", "https://developer.android.com/studio/run/emulator-acceleration", "Live documentation; includes deprecated GPU modes")
