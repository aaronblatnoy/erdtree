"""finetune/scenarios_v3/hardware.py — corpus v3 multi-turn scenarios for 'hardware'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="hardware-v3-0001", tool="hardware", kind="followup", turns=(
        Turn(user_input="show me the cpu topology on this host", tool="hardware", operation="cpu", args={"operation": "cpu"}),
        Turn(user_input="also show how much ram is free", tool="hardware", operation="memory", args={"operation": "memory"}),
    )),
    V3(id="hardware-v3-0002", tool="hardware", kind="followup", turns=(
        Turn(user_input="list the pci devices on this box", tool="hardware", operation="pci", args={"operation": "pci"}),
        Turn(user_input="now the usb bus too", tool="hardware", operation="usb", args={"operation": "usb"}),
    )),
    V3(id="hardware-v3-0003", tool="hardware", kind="followup", turns=(
        Turn(user_input="check the sensor readings, I'm worried about temps", tool="hardware", operation="sensors", args={"operation": "sensors"}),
        Turn(user_input="pull cpu info too so I can compare against the throttle threshold", tool="hardware", operation="cpu", args={"operation": "cpu"}),
    )),
    V3(id="hardware-v3-0004", tool="hardware", kind="followup", turns=(
        Turn(user_input="show block device topology", tool="hardware", operation="block", args={"operation": "block"}),
        Turn(user_input="that disk layout is fine, check memory usage instead", tool="hardware", operation="memory", args={"operation": "memory"}),
    )),
    V3(id="hardware-v3-0005", tool="hardware", kind="followup", turns=(
        Turn(user_input="give me a full hardware summary", tool="hardware", operation="summary", args={"operation": "summary"}),
        Turn(user_input="drill into the sensors, that memory number worried me", tool="hardware", operation="sensors", args={"operation": "sensors"}),
    )),
    V3(id="hardware-v3-0006", tool="hardware", kind="followup", turns=(
        Turn(user_input="list pci bus devices", tool="hardware", operation="pci", args={"operation": "pci"}),
        Turn(user_input="cross-check that against the kernel modules currently loaded", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
    )),
    V3(id="hardware-v3-0007", tool="hardware", kind="followup", turns=(
        Turn(user_input="show cpu capability info", tool="hardware", operation="cpu", args={"operation": "cpu"}),
        Turn(user_input="also grab a block device listing", tool="hardware", operation="block", args={"operation": "block"}),
        Turn(user_input="also the sensor readings on top of that", tool="hardware", operation="sensors", args={"operation": "sensors"}),
    )),
    V3(id="hardware-v3-0008", tool="hardware", kind="followup", turns=(
        Turn(user_input="what usb devices are attached right now", tool="hardware", operation="usb", args={"operation": "usb"}),
        Turn(user_input="do the same for pci", tool="hardware", operation="pci", args={"operation": "pci"}),
    )),
    V3(id="hardware-v3-0009", tool="hardware", kind="followup", turns=(
        Turn(user_input="check ram and swap usage", tool="hardware", operation="memory", args={"operation": "memory"}),
        Turn(user_input="ok that's tight, show block devices so I can see if swap has room to grow", tool="hardware", operation="block", args={"operation": "block"}),
        Turn(user_input="also the combined summary view", tool="hardware", operation="summary", args={"operation": "summary"}),
    )),
    V3(id="hardware-v3-0010", tool="hardware", kind="question", turns=(
        Turn(user_input="show me the sensor readings for this machine", tool="hardware", operation="sensors", args={"operation": "sensors"}),
        Turn(user_input="is that 82 degrees on the package sensor a problem", answer="82C under load is within spec for most desktop CPU types but is getting close to thermal throttling territory (usually 90-100C). Worth checking airflow and fan curves if it's sustained at idle or light load; a short spike under heavy load is normal."),
    )),
    V3(id="hardware-v3-0011", tool="hardware", kind="question", turns=(
        Turn(user_input="give me the full hardware summary", tool="hardware", operation="summary", args={"operation": "summary"}),
        Turn(user_input="what should I look at first if this server feels slow", answer="Start with memory pressure (swap usage climbing means the box is thrashing) and disk saturation on the block devices. If both look clean, check CPU topology for core count versus what's actually running before assuming a hardware limit."),
    )),
    V3(id="hardware-v3-0012", tool="hardware", kind="question", turns=(
        Turn(user_input="list pci devices", tool="hardware", operation="pci", args={"operation": "pci"}),
        Turn(user_input="what does it mean if a device shows no kernel driver in use", answer="No driver bound means the OS sees the device but hasn't loaded a module for it, so it's inert. That's normal for things like unused USB controllers, but for a NIC or GPU it usually means the driver package is missing or blacklisted and needs to be installed or reloaded."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("hardware", SCENARIOS_V3)
