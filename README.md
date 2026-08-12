## Logifer

This simple tool just gathers logs from android devices

It simply runs adb logcat -b all, adb shell dmesg and puts the outputs in a logcat.txt and dmesg.txt file.
Also it attempts to put only errors and issues in logcat_filtered.txt

Also if you run log.py -k it attempts to get last_kmsg by running adb pull /proc/last_kmsg but doesn't get the other logs
(since -k is meant to only run in Custom Recoveries like TWRP, OFOX, PBRP etc.)

WARNING THIS TOOL IS ENTIRELY VIBECODED!!
