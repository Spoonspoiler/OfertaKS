[app]
title = OfertaKS
package.name = ofertaks
package.domain = com.ptitspot
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,txt,md
version = 0.1.0
requirements = python3,kivy,requests,beautifulsoup4,pypdf,certifi,plyer
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 35
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
