"""finetune/scenarios_v3/dnf_modules.py — corpus v3 multi-turn scenarios for 'dnf_modules'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="dnf_modules-v3-0001", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="list the available streams for nodejs", tool="dnf_modules", operation="list",
             args={"operation": "list", "module": "nodejs"}),
        Turn(user_input="and postgresql too", tool="dnf_modules", operation="list",
             args={"operation": "list", "module": "postgresql"}),
    )),
    V3(id="dnf_modules-v3-0002", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="show details on nodejs:18", tool="dnf_modules", operation="info",
             args={"operation": "info", "module": "nodejs:18"}),
        Turn(user_input="ok, now enable it", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "nodejs:18"}),
    )),
    V3(id="dnf_modules-v3-0003", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="enable the php:8.1 module stream", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "php:8.1"}),
        Turn(user_input="yes go ahead and install the common profile", tool="dnf_modules", operation="install",
             args={"operation": "install", "module": "php:8.1/common"}),
        Turn(user_input="and now show what got installed", tool="dnf_modules", operation="info",
             args={"operation": "info", "module": "php:8.1/common"}),
    )),
    V3(id="dnf_modules-v3-0004", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="enable postgresql:15", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "postgresql:15"}),
        Turn(user_input="no, use the other stream instead, 16", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "postgresql:16"}),
    )),
    V3(id="dnf_modules-v3-0005", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="install the ruby:3.1/common profile", tool="dnf_modules", operation="install",
             args={"operation": "install", "module": "ruby:3.1/common"}),
        Turn(user_input="what happened, search for the ruby package to confirm", tool="packages", operation="search",
             args={"operation": "search", "keyword": "ruby"}),
    )),
    V3(id="dnf_modules-v3-0006", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="disable the mariadb module stream", tool="dnf_modules", operation="disable",
             args={"operation": "disable", "module": "mariadb"}),
        Turn(user_input="undo that, reset it back to default instead", tool="dnf_modules", operation="reset",
             args={"operation": "reset", "module": "mariadb"}),
    )),
    V3(id="dnf_modules-v3-0007", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="give me info on the go-toolset:rhel8 module", tool="dnf_modules", operation="info",
             args={"operation": "info", "module": "go-toolset:rhel8"}),
        Turn(user_input="the same for llvm-toolset", tool="dnf_modules", operation="info",
             args={"operation": "info", "module": "llvm-toolset"}),
    )),
    V3(id="dnf_modules-v3-0008", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="reset the nodejs module", tool="dnf_modules", operation="reset",
             args={"operation": "reset", "module": "nodejs"}),
        Turn(user_input="ok do it, then enable nodejs:20 fresh", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "nodejs:20"}),
        Turn(user_input="also install the development profile for that one", tool="dnf_modules", operation="install",
             args={"operation": "install", "module": "nodejs:20/development"}),
    )),
    V3(id="dnf_modules-v3-0009", tool="dnf_modules", kind="followup", turns=(
        Turn(user_input="enable python39 stream", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "python39"}),
        Turn(user_input="install it now", tool="dnf_modules", operation="install",
             args={"operation": "install", "module": "python39/common"}),
    )),
    V3(id="dnf_modules-v3-0010", tool="dnf_modules", kind="question", turns=(
        Turn(user_input="show info on the nginx:1.24 module stream", tool="dnf_modules", operation="info",
             args={"operation": "info", "module": "nginx:1.24"}),
        Turn(user_input="what do those profiles in the listing mean", answer=(
            "The profiles are named installation sets for that stream, such as "
            "common or minimal, each pulling in a different group of packages. "
            "Pick one with dnf_modules install using module:stream/profile."
        )),
    )),
    V3(id="dnf_modules-v3-0011", tool="dnf_modules", kind="question", turns=(
        Turn(user_input="enable the mysql:8.0 module stream", tool="dnf_modules", operation="enable",
             args={"operation": "enable", "module": "mysql:8.0"}),
        Turn(user_input="why did it warn about a stream switch", answer=(
            "Enabling a stream when a different one for the same module was already "
            "enabled forces a switch, which can conflict with anything already installed "
            "from the old stream. Reset the module first if packages from mysql:5.7 are present."
        )),
    )),
    V3(id="dnf_modules-v3-0012", tool="dnf_modules", kind="question", turns=(
        Turn(user_input="disable the postgresql module stream", tool="dnf_modules", operation="disable",
             args={"operation": "disable", "module": "postgresql"}),
        Turn(user_input="what does disabling it actually change", answer=(
            "Disabling marks the module off-limits for installs, but any postgresql "
            "packages already on the box stay installed and running. Remove those "
            "packages separately if you want them gone too."
        )),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("dnf_modules", SCENARIOS_V3)
