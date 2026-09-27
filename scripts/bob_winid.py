#!/usr/bin/env python3
"""Resolve the CGWindowID of the IBM Bob main window (no PyObjC needed)."""
import ctypes
import ctypes.util
import sys

cg = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
)
cf = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)

cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
cf.CFArrayGetCount.restype = ctypes.c_long
cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
cf.CFDictionaryGetValue.restype = ctypes.c_void_p
cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
cf.CFNumberGetValue.restype = ctypes.c_bool
cf.CFRelease.argtypes = [ctypes.c_void_p]

cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p

KCFStringEncodingUTF8 = 0x08000100
KCGWindowListOptionAll = 0x0000001B
KEY_OWNER = cf.CFStringCreateWithCString(None, b"kCGWindowOwnerName", KCFStringEncodingUTF8)
KEY_NUMBER = cf.CFStringCreateWithCString(None, b"kCGWindowNumber", KCFStringEncodingUTF8)
KEY_BOUNDS = cf.CFStringCreateWithCString(None, b"kCGWindowBounds", KCFStringEncodingUTF8)
KEY_LAYER = cf.CFStringCreateWithCString(None, b"kCGWindowLayer", KCFStringEncodingUTF8)
KEY_NAME = cf.CFStringCreateWithCString(None, b"kCGWindowName", KCFStringEncodingUTF8)


def cfstr_to_str(ptr):
    if not ptr:
        return ""
    buf = ctypes.create_string_buffer(1024)
    ok = cf.CFStringGetCString(ptr, buf, 1024, KCFStringEncodingUTF8) if hasattr(cf, "CFStringGetCString") else 0
    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    cf.CFStringGetCString.restype = ctypes.c_bool
    ok = cf.CFStringGetCString(ptr, buf, 1024, KCFStringEncodingUTF8)
    return buf.value.decode("utf-8", "replace") if ok else ""


def get_number(num_ptr):
    val = ctypes.c_double(0)
    cf.CFNumberGetValue(num_ptr, 13, ctypes.byref(val))  # 13 = kCFNumberFloat64Type... use int64
    i = ctypes.c_longlong(0)
    cf.CFNumberGetValue(num_ptr, 4, ctypes.byref(i))  # 4 = kCFNumberSInt64Type
    return int(i.value if hasattr(i, "value") else i)


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else "IBM Bob"
    arr = cg.CGWindowListCopyWindowInfo(KCGWindowListOptionAll, 0)
    n = cf.CFArrayGetCount(arr)
    best = None
    for i in range(n):
        d = cf.CFArrayGetValueAtIndex(arr, i)
        owner = cfstr_to_str(cf.CFDictionaryGetValue(d, KEY_OWNER))
        if owner.lower() != want.lower():
            continue
        wid = get_number(cf.CFDictionaryGetValue(d, KEY_NUMBER))
        layer = get_number(cf.CFDictionaryGetValue(d, KEY_LAYER))
        name = cfstr_to_str(cf.CFDictionaryGetValue(d, KEY_NAME))
        bnd = cf.CFDictionaryGetValue(d, KEY_BOUNDS)
        w = h = 0
        if bnd:
            for k, out in ((b"Width", "w"), (b"Height", "h")):
                kp = cf.CFStringCreateWithCString(None, k, KCFStringEncodingUTF8)
                vp = cf.CFDictionaryGetValue(bnd, kp)
                if vp:
                    if out == "w":
                        w = get_number(vp)
                    else:
                        h = get_number(vp)
        print(f"winid={wid} layer={layer} name={name!r} {w}x{h}")
        if layer == 0 and (best is None or w * h > best[1]):
            best = (wid, w * h)
    if best:
        print(f"BEST {best[0]}")


if __name__ == "__main__":
    main()
