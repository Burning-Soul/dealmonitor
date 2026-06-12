[app]
title = 618 比价监测
package.name = dealmonitor
package.domain = com.dealmonitor
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,ttc,otf,html,js,css
version = 1.0
requirements = python3,kivy==2.3.1,plyer,pillow
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,POST_NOTIFICATIONS,VIBRATE,SCHEDULE_EXACT_ALARM,USE_EXACT_ALARM,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,RECEIVE_BOOT_COMPLETED,WAKE_LOCK,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
android.api = 34
android.minapi = 26
android.ndk = 25b
android.sdk = 34
android.arch = arm64-v8a
android.allow_backup = True
android.foreground_service_type = dataSync
presplash_color = #1a1a2e
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1