#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$here/../.." && pwd)
cd "$repo/android_app/HybridGuard"
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
./gradlew :featureapp:testDebugUnitTest :featureapp:assembleDebug \
  -PhybridguardRequirePublicEndpoints=false \
  -PhybridguardCollectEndpoint=http://127.0.0.1:8765/api/collect/fingerprint \
  -PhybridguardBrowserTicketEndpoint=http://127.0.0.1:8765/api/collect/browser-ticket \
  -PhybridguardBrowserPairPollBaseUrl=http://127.0.0.1:8765/api/collect/browser-pairs \
  -PhybridguardBrowserProbeBaseUrl=http://127.0.0.1:8765/
mkdir -p "$here/runtime"
cp featureapp/build/outputs/apk/debug/featureapp-debug.apk "$here/runtime/featureapp-v13-local-only.apk"
