---
name: PyQt desktop runtime
description: Native runtime dependencies needed for PyQt desktop workflows in the Replit Linux environment.
---

For PyQt applications launched through a VNC workflow, declare the Qt xcb runtime libraries as Nix system dependencies rather than relying only on the Python wheels.

**Why:** The PyQt wheel includes the xcb platform plugin, but the host does not necessarily expose its X11, xcb-util, xkbcommon, and dbus shared-library dependencies. Without them, the application exits before creating a QApplication.

**How to apply:** When configuring or repairing a PyQt VNC workflow, check the xcb plugin with `ldd` and ensure the corresponding Nix X11/runtime packages are installed before diagnosing application code.