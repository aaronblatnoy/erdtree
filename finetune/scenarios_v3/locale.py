"""finetune/scenarios_v3/locale.py — corpus v3 multi-turn scenarios for 'locale'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="locale-v3-0001", tool="locale", kind="followup", turns=(
        Turn(user_input="what timezone is this box on", tool="locale", operation="timedatectl-status",
             args={"operation": "timedatectl-status"}),
        Turn(user_input="set it to America/Chicago", tool="locale", operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "America/Chicago"}),
    )),
    V3(id="locale-v3-0002", tool="locale", kind="followup", turns=(
        Turn(user_input="set the system locale to en_US.UTF-8", tool="locale", operation="set-locale",
             args={"operation": "set-locale", "locale": "en_US.UTF-8"}),
        Turn(user_input="do the same for de_DE.UTF-8", tool="locale", operation="set-locale",
             args={"operation": "set-locale", "locale": "de_DE.UTF-8"}),
    )),
    V3(id="locale-v3-0003", tool="locale", kind="followup", turns=(
        Turn(user_input="show the current locale and keymap settings", tool="locale", operation="localectl-status",
             args={"operation": "localectl-status"}),
        Turn(user_input="ok, switch the keymap to gb", tool="locale", operation="set-keymap",
             args={"operation": "set-keymap", "keymap": "gb"}),
        Turn(user_input="yes go ahead, also enable ntp now", tool="locale", operation="set-ntp",
             args={"operation": "set-ntp", "enabled": "true"}),
    )),
    V3(id="locale-v3-0004", tool="locale", kind="followup", turns=(
        Turn(user_input="turn off ntp sync on this host", tool="locale", operation="set-ntp",
             args={"operation": "set-ntp", "enabled": "false"}),
        Turn(user_input="undo that, turn it back on", tool="locale", operation="set-ntp",
             args={"operation": "set-ntp", "enabled": "true"}),
    )),
    V3(id="locale-v3-0005", tool="locale", kind="followup", turns=(
        Turn(user_input="set the timezone to UTC", tool="locale", operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "UTC"}),
        Turn(user_input="no, use Europe/London instead", tool="locale", operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "Europe/London"}),
    )),
    V3(id="locale-v3-0006", tool="locale", kind="followup", turns=(
        Turn(user_input="set the keyboard layout to us", tool="locale", operation="set-keymap",
             args={"operation": "set-keymap", "keymap": "us"}),
        Turn(user_input="and now check the time sync status", tool="locale", operation="timedatectl-status",
             args={"operation": "timedatectl-status"}),
    )),
    V3(id="locale-v3-0007", tool="locale", kind="followup", turns=(
        Turn(user_input="check ntp sync status", tool="locale", operation="timedatectl-status",
             args={"operation": "timedatectl-status"}),
        Turn(user_input="why is it not synced, look at chrony's own status too", tool="chrony", operation="tracking",
             args={"operation": "tracking"}),
    )),
    V3(id="locale-v3-0008", tool="locale", kind="followup", turns=(
        Turn(user_input="set locale to fr_FR.UTF-8", tool="locale", operation="set-locale",
             args={"operation": "set-locale", "locale": "fr_FR.UTF-8"}),
        Turn(user_input="also set the keymap to fr", tool="locale", operation="set-keymap",
             args={"operation": "set-keymap", "keymap": "fr"}),
        Turn(user_input="confirm the change took by showing current status", tool="locale", operation="localectl-status",
             args={"operation": "localectl-status"}),
    )),
    V3(id="locale-v3-0009", tool="locale", kind="followup", turns=(
        Turn(user_input="set the timezone to Asia/Tokyo", tool="locale", operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "Asia/Tokyo"}),
        Turn(user_input="do it", tool="locale", operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "Asia/Tokyo"}),
    )),
    V3(id="locale-v3-0010", tool="locale", kind="question", turns=(
        Turn(user_input="show localectl status", tool="locale", operation="localectl-status",
             args={"operation": "localectl-status"}),
        Turn(user_input="what does that VC keymap field mean versus the X11 one", answer=(
            "VC Keymap is the layout used at the virtual console (before X starts), "
            "while X11 Layout applies once a graphical session is running. They can "
            "be set independently, so mismatches between them are normal."
        )),
    )),
    V3(id="locale-v3-0011", tool="locale", kind="question", turns=(
        Turn(user_input="set ntp enabled to true", tool="locale", operation="set-ntp",
             args={"operation": "set-ntp", "enabled": "true"}),
        Turn(user_input="why didn't the clock jump right after that", answer=(
            "Enabling NTP only starts the sync service, it does not force an instant "
            "jump; it converges gradually. Check timedatectl-status to confirm the "
            "System clock synchronized field flips to yes."
        )),
    )),
    V3(id="locale-v3-0012", tool="locale", kind="question", turns=(
        Turn(user_input="set the timezone to America/Denver", tool="locale", operation="set-timezone",
             args={"operation": "set-timezone", "timezone": "America/Denver"}),
        Turn(user_input="does that change require a reboot", answer=(
            "No, changing the timezone takes effect immediately for new timestamps. "
            "Long-running processes that cached the old offset, such as cron or logging "
            "daemons, may need a restart to pick it up cleanly."
        )),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("locale", SCENARIOS_V3)
