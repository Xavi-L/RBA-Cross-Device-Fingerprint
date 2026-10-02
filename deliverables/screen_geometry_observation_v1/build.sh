#!/bin/zsh
set -euo pipefail
here=${0:A:h}
repo=${here:h:h}
out=${1:-$here}
mkdir -p "$out/runtime"
out=${out:A}
version=$(sed -n 's/.*versionCode = \([0-9][0-9]*\).*/\1/p' "$repo/android_app/HybridGuard/featureapp/build.gradle.kts")
[[ "$version" == <-> ]] || { print -u2 'Cannot read a unique numeric versionCode'; exit 2; }
apk="$out/runtime/featureapp-v${version}-geometry-local-only.apk"
log="$out/runtime/build-v${version}.log"
record="$out/BUILD_v${version}.json"
[[ ! -e "$apk" && ! -e "$log" && ! -e "$record" ]] || { print -u2 'Build outputs already exist; choose a new output directory'; exit 2; }
build_root=$(mktemp -d "/tmp/screen-geometry-v${version}.XXXXXX")
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export ANDROID_SDK_ROOT="$HOME/Library/Android/sdk"
cd "$repo/android_app/HybridGuard"
./gradlew --no-daemon --console=plain --project-cache-dir "$build_root/project-cache" \
  -I "$here/isolated_build.gradle" -DgeometryBuildRoot="$build_root/build" \
  -PhybridguardCollectEndpoint=http://127.0.0.1:8000/api/collect/fingerprint -PhybridguardRequirePublicEndpoints=false \
  :featureapp:testDebugUnitTest :featureapp:assembleDebug > "$log" 2>&1
cp "$build_root/build/featureapp/outputs/apk/debug/featureapp-debug.apk" "$apk"
python3 - "$build_root" "$out" "$version" <<'PY'
import json,sys,xml.etree.ElementTree as ET
from pathlib import Path
root,out=map(Path,sys.argv[1:3]);version=int(sys.argv[3]);tests=[]
for path in (root/'build/featureapp/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 e=ET.parse(path).getroot();tests.append({k:e.attrib.get(k) for k in ('name','tests','failures','errors','skipped','time')})
(out/f'BUILD_v{version}.json').write_text(json.dumps({'build_root':str(root),'command':f'zsh deliverables/screen_geometry_observation_v1/build.sh {out}', 'version_code':version,'java':'21','model_fit_calls':0,'apk':f'runtime/featureapp-v{version}-geometry-local-only.apk','tests':tests,'tests_total':sum(int(t['tests']) for t in tests),'failures':sum(int(t['failures'])+int(t['errors']) for t in tests),'existing_build_outputs_used':False},indent=2)+'\n')
print('APK copied; JUnit tests:',sum(int(t['tests']) for t in tests))
PY
