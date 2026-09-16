"""finetune/scenarios_v3/grub.py — corpus v3 multi-turn scenarios for 'grub'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="grub-v3-0001", tool="grub", kind="followup", turns=(
        Turn(user_input="show the current default boot kernel", tool="grub", operation="default-kernel", args={"operation": "default-kernel"}),
        Turn(user_input="show me its full entry details", tool="grub", operation="info", args={"operation": "info", "kernel": "ALL"}),
    )),
    V3(id="grub-v3-0002", tool="grub", kind="followup", turns=(
        Turn(user_input="add 'nomodeset' to the kernel args on /boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64", tool="grub", operation="args-add", args={"operation": "args-add", "kernel": "/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64", "kernel_args": "nomodeset"}),
        Turn(user_input="do the same for /boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64", tool="grub", operation="args-add", args={"operation": "args-add", "kernel": "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64", "kernel_args": "nomodeset"}),
    )),
    V3(id="grub-v3-0003", tool="grub", kind="followup", turns=(
        Turn(user_input="remove 'quiet splash' from the args on /boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64", tool="grub", operation="args-remove", args={"operation": "args-remove", "kernel": "/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64", "kernel_args": "quiet splash"}),
        Turn(user_input="confirm it, show me the entry details", tool="grub", operation="info", args={"operation": "info", "kernel": "/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64"}),
    )),
    V3(id="grub-v3-0004", tool="grub", kind="followup", turns=(
        Turn(user_input="set the default boot kernel to /boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64", tool="grub", operation="set-default", args={"operation": "set-default", "kernel": "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64"}),
        Turn(user_input="not that one, use /boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64 instead", tool="grub", operation="set-default", args={"operation": "set-default", "kernel": "/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64"}),
    )),
    V3(id="grub-v3-0005", tool="grub", kind="followup", turns=(
        Turn(user_input="set the GRUB bootloader password to a new value 'R9!vault-42q'", tool="grub", operation="set-password", args={"operation": "set-password", "password": "R9!vault-42q"}),
        Turn(user_input="ok now regenerate the config so it takes effect", tool="grub", operation="mkconfig", args={"operation": "mkconfig"}),
    )),
    V3(id="grub-v3-0006", tool="grub", kind="followup", turns=(
        Turn(user_input="show me all the grub boot entries", tool="grub", operation="info", args={"operation": "info", "kernel": "ALL"}),
        Turn(user_input="also regenerate the config to /boot/grub2/grub.cfg.new for review first", tool="grub", operation="mkconfig", args={"operation": "mkconfig", "output_file": "/boot/grub2/grub.cfg.new"}),
    )),
    V3(id="grub-v3-0007", tool="grub", kind="followup", turns=(
        Turn(user_input="remove the kernel entry for /boot/vmlinuz-5.14.0-284.11.1.el9_2.x86_64", tool="grub", operation="remove-kernel", args={"operation": "remove-kernel", "kernel": "/boot/vmlinuz-5.14.0-284.11.1.el9_2.x86_64"}),
        Turn(user_input="also what is the default boot kernel now", tool="grub", operation="default-kernel", args={"operation": "default-kernel"}),
    )),
    V3(id="grub-v3-0008", tool="grub", kind="followup", turns=(
        Turn(user_input="check what kernel modules are currently loaded", tool="kernel_modules", operation="lsmod", args={"operation": "lsmod"}),
        Turn(user_input="also show the boot entry details for the running kernel", tool="grub", operation="info", args={"operation": "info", "kernel": "ALL"}),
    )),
    V3(id="grub-v3-0009", tool="grub", kind="followup", turns=(
        Turn(user_input="add 'crashkernel=256M' to /boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64", tool="grub", operation="args-add", args={"operation": "args-add", "kernel": "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64", "kernel_args": "crashkernel=256M"}),
        Turn(user_input="now set that same kernel as the default", tool="grub", operation="set-default", args={"operation": "set-default", "kernel": "/boot/vmlinuz-5.14.0-427.13.1.el9_4.x86_64"}),
        Turn(user_input="and then regenerate the grub config to make it stick", tool="grub", operation="mkconfig", args={"operation": "mkconfig"}),
    )),
    V3(id="grub-v3-0010", tool="grub", kind="question", turns=(
        Turn(user_input="show the default boot kernel path", tool="grub", operation="default-kernel", args={"operation": "default-kernel"}),
        Turn(user_input="what does that path actually tell me", answer="That's the exact vmlinuz file GRUB boots by default on the next reboot. If it doesn't match the kernel version you expect (check with uname -r after a reboot), the default entry needs to be repointed with set-default."),
    )),
    V3(id="grub-v3-0011", tool="grub", kind="question", turns=(
        Turn(user_input="regenerate the grub config file", tool="grub", operation="mkconfig", args={"operation": "mkconfig"}),
        Turn(user_input="why is that risky to run", answer="mkconfig rewrites grub.cfg from the templates in /etc/grub.d and /etc/default/grub. A bad template, a missing device.map entry, or an interrupted write can leave the host unable to find a bootable entry. Keep a copy of the old grub.cfg before running it on anything you can't walk up to."),
    )),
    V3(id="grub-v3-0012", tool="grub", kind="question", turns=(
        Turn(user_input="remove the kernel entry for /boot/vmlinuz-5.14.0-70.13.1.el9_0.x86_64", tool="grub", operation="remove-kernel", args={"operation": "remove-kernel", "kernel": "/boot/vmlinuz-5.14.0-70.13.1.el9_0.x86_64"}),
        Turn(user_input="what happens if that was the only kernel left", answer="If that was the last bootable entry, the system has no valid GRUB target and will fail to boot. Always confirm with default-kernel or info first that at least one other installed kernel remains before removing an entry."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("grub", SCENARIOS_V3)
