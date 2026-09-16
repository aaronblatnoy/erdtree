"""finetune/scenarios_v3/rpm.py — corpus v3 multi-turn scenarios for 'rpm'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="rpm-v3-0001", tool="rpm", kind="followup", turns=(
        Turn(user_input="show me the package info for openssl-libs", tool="rpm", operation="query_info",
             args={"operation": "query_info", "package": "openssl-libs"}),
        Turn(user_input="now the same for openssl", tool="rpm", operation="query_info",
             args={"operation": "query_info", "package": "openssl"}),
    )),
    V3(id="rpm-v3-0002", tool="rpm", kind="followup", turns=(
        Turn(user_input="list the files owned by httpd", tool="rpm", operation="query_files",
             args={"operation": "query_files", "package": "httpd"}),
        Turn(user_input="and httpd-tools too", tool="rpm", operation="query_files",
             args={"operation": "query_files", "package": "httpd-tools"}),
    )),
    V3(id="rpm-v3-0003", tool="rpm", kind="followup", turns=(
        Turn(user_input="which package owns /usr/bin/curl", tool="rpm", operation="query_file",
             args={"operation": "query_file", "file": "/usr/bin/curl"}),
        Turn(user_input="ok, now verify that package's files against the rpm database", tool="rpm", operation="verify",
             args={"operation": "verify", "package": "curl"}),
    )),
    V3(id="rpm-v3-0004", tool="rpm", kind="followup", turns=(
        Turn(user_input="check the gpg signature on /tmp/nginx-1.25.3-1.el9.x86_64.rpm", tool="rpm", operation="checksig",
             args={"operation": "checksig", "rpm_file": "/tmp/nginx-1.25.3-1.el9.x86_64.rpm"}),
        Turn(user_input="signature's good, go ahead and install it", tool="rpm", operation="install",
             args={"operation": "install", "rpm_file": "/tmp/nginx-1.25.3-1.el9.x86_64.rpm"}),
    )),
    V3(id="rpm-v3-0005", tool="rpm", kind="followup", turns=(
        Turn(user_input="verify the vim-enhanced package files", tool="rpm", operation="verify",
             args={"operation": "verify", "package": "vim-enhanced"}),
        Turn(user_input="also check who owns /etc/vimrc from that same install", tool="rpm", operation="query_file",
             args={"operation": "query_file", "file": "/etc/vimrc"}),
    )),
    V3(id="rpm-v3-0006", tool="rpm", kind="followup", turns=(
        Turn(user_input="install /root/downloads/custom-fleet-tools-2.1-1.x86_64.rpm", tool="rpm", operation="install",
             args={"operation": "install", "rpm_file": "/root/downloads/custom-fleet-tools-2.1-1.x86_64.rpm"}),
        Turn(user_input="hold off on that, check the checksum signature first before installing", tool="rpm", operation="checksig",
             args={"operation": "checksig", "rpm_file": "/root/downloads/custom-fleet-tools-2.1-1.x86_64.rpm"}),
    )),
    V3(id="rpm-v3-0007", tool="rpm", kind="followup", turns=(
        Turn(user_input="pull the cpio payload out of /var/cache/dnf/downloads/postgresql16-16.2-1.rpm", tool="rpm", operation="rpm2cpio",
             args={"operation": "rpm2cpio", "rpm_file": "/var/cache/dnf/downloads/postgresql16-16.2-1.rpm"}),
        Turn(user_input="also show the installed package info for postgresql16 for comparison", tool="rpm", operation="query_info",
             args={"operation": "query_info", "package": "postgresql16"}),
    )),
    V3(id="rpm-v3-0008", tool="rpm", kind="followup", turns=(
        Turn(user_input="check which package owns /etc/sudoers", tool="rpm", operation="query_file",
             args={"operation": "query_file", "file": "/etc/sudoers"}),
        Turn(user_input="check that package's cron.d cleanup job next", tool="cron", operation="crond-view",
             args={"operation": "crond-view"}),
    )),
    V3(id="rpm-v3-0009", tool="rpm", kind="followup", turns=(
        Turn(user_input="query files owned by kernel-tools", tool="rpm", operation="query_files",
             args={"operation": "query_files", "package": "kernel-tools"}),
        Turn(user_input="get the full info on that package next", tool="rpm", operation="query_info",
             args={"operation": "query_info", "package": "kernel-tools"}),
        Turn(user_input="now verify it against the database", tool="rpm", operation="verify",
             args={"operation": "verify", "package": "kernel-tools"}),
    )),
    V3(id="rpm-v3-0010", tool="rpm", kind="question", turns=(
        Turn(user_input="verify all installed packages", tool="rpm", operation="verify", args={"operation": "verify"}),
        Turn(user_input="in that output, what do the letter codes actually mean",
             answer="Each column flags a specific mismatch against the rpm database: S is size, M is mode/permissions, 5 is checksum, T is mtime, and so on; a dot means that check passed. A 'c' before the filename marks it as a config file, which often changes legitimately after install."),
    )),
    V3(id="rpm-v3-0011", tool="rpm", kind="question", turns=(
        Turn(user_input="check the signature on /tmp/vendor-driver-3.2.rpm", tool="rpm", operation="checksig",
             args={"operation": "checksig", "rpm_file": "/tmp/vendor-driver-3.2.rpm"}),
        Turn(user_input="is it safe to install if that comes back unsigned",
             answer="Not automatically. An unsigned package could still be legitimate if the vendor just doesn't sign builds, but it also means rpm can't verify it wasn't tampered with in transit. Confirm the source and checksum out of band before installing anything that comes back unsigned."),
    )),
    V3(id="rpm-v3-0012", tool="rpm", kind="question", turns=(
        Turn(user_input="show package info for glibc", tool="rpm", operation="query_info",
             args={"operation": "query_info", "package": "glibc"}),
        Turn(user_input="what's the risk of removing that",
             answer="Removing glibc would break nearly every dynamically linked binary on the system including the package manager itself, so the box would become unusable and likely unrecoverable without a rescue image. It should never be targeted for removal on a running system."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("rpm", SCENARIOS_V3)
