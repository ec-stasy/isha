import re
from command_ir import CommandIR

# ---------------------------------------------------------------------------------------
# various types/shapes of command...
# help in handling different types of commands according to their specific shape

# words acting just as fillers (to be skipped)
SKIP_WORDS = {
    "to", "at", "the", "a", "an", "by",
    "for", "of", "please", "isha",
    "can", "could", "would", "should",
    "i", "me", "my", "we",
    "just", "now", "quickly", "asap",
    "this", "that", "it",
    "hey", "hi", "ok", "okay",
    "kya", "mujhe", "mera", "mere",     # hinglish skip words
    "zara", "thoda", "please",
    "mode",                             # independent check by resolve_mode()
    "pomodoro",                         # domain marker for start_pomodoro's free target (mode name)
    "as",                               # connector for "alias browser as chrome"
}

# for mapping various synonyms to valid action verbs in the system
# direct lookup (action enough. no target needed)
VERB_ACTION_MAP = {
    # app commands
    "open": "open_app",
    "launch": "open_app",
    "start": "open_app",
    "run": "open_app",
    "load": "open_app",
    "boot": "open_app",
    "execute": "open_app",
    "fire": "open_app",
    "fire up": "open_app",
    "pull up": "open_app",
    "bring up": "open_app",
    "open up": "open_app",
    "spin up": "open_app",
    "wake": "open_app",
    "initialize": "open_app",
    "initialise": "open_app",
    "deploy": "open_app",
    "shuru": "open_app",        # hinglish: start
    "shuru karo": "open_app",
    "chala": "open_app",        # hinglish: run
    "chalao": "open_app",
    "chalu": "open_app",
    "khol": "open_app",
    "kholo": "open_app",
    "activate": "open_app",
    "enable": "open_app",
    "enter": "open_app",
    "turn on": "open_app",
    "begin": "open_app",
    "start karo": "open_app",     # hinglish

    "close": "close_app",
    "quit": "close_app",
    "exit": "close_app",
    "kill": "close_app",
    "stop": "close_app",
    "terminate": "close_app",
    "end": "close_app",
    "shut": "close_app",
    "force quit": "close_app",
    "force close": "close_app",
    "kill off": "close_app",
    "close out": "close_app",
    "close down": "close_app",
    "shut down app": "close_app",
    "band": "close_app",        # hinglish: close
    "bund": "close_app",
    "band karo": "close_app",
    "bund karo": "close_app",
    "hatao": "close_app",       # hinglish: remove/close
    "deactivate": "close_app",
    "disable": "close_app",
    "leave": "close_app",

    # increase/decrease value (brightness, volume, etc.)
    #_value
    "increase": "increase_value",
    "raise": "increase_value",
    "brighten": "increase_value",
    "boost": "increase_value",
    "up": "increase_value",
    "crank up": "increase_value",
    "turn up": "increase_value",
    "bump up": "increase_value",
    "max": "increase_value",
    "maximize": "increase_value",
    "badhao": "increase_value",    # hinglish: increase
    "tej karo": "increase_value",  # hinglish: make brighter

    "decrease": "decrease_value",
    "lower": "decrease_value",
    "dim": "decrease_value",
    "reduce": "decrease_value",
    "tone down": "decrease_value",
    "turn down": "decrease_value",
    "darken": "decrease_value",
    "dull": "decrease_value",
    "kam karo": "decrease_value",  # hinglish: reduce
    "ghataao": "decrease_value",   # hinglish: decrease

    # set value to a specific level
    "set": "set_value",
    "put": "set_value",
    "change": "set_value",
    "adjust": "set_value",
    "configure": "set_value",
    "fix": "set_value",
    "assign": "set_value",
    "karo": "set_value",                # hinglish: do/set
    "kar": "set_value",
    "laga": "set_value",                # hinglish: set/apply
    "lagao": "set_value",
    "rakh": "set_value",                # hinglish: keep/set
    "rakho": "set_value",

    # volume
    "mute": "mute_volume",
    "silence": "mute_volume",
    "quiet": "mute_volume",
    "quieten": "mute_volume",
    "hush": "mute_volume",
    "shush": "mute_volume",
    "shut up": "mute_volume",
    "chup": "mute_volume",              # hinglish: be quiet
    "chup karo": "mute_volume",
    "band karo awaaz": "mute_volume",   # hinglish: turn off sound

    "unmute": "unmute_volume",
    "unsilence": "unmute_volume",
    "restore sound": "unmute_volume",
    "turn on sound": "unmute_volume",
    "awaaz chalu karo": "unmute_volume", # hinglish: turn on sound

    # toggle/flip a value between states
    "toggle": "toggle_value",
    "flip": "toggle_value",
    "switch": "toggle_value",
    "swap": "toggle_value",

    # system actions
    "shutdown": "shutdown",
    "shut down": "shutdown",
    "power off": "shutdown",
    "turn off": "shutdown",
    "switch off": "shutdown",
    "power down": "shutdown",
    "band kar": "shutdown",             # hinglish
    "off kar": "shutdown",

    "restart": "restart",
    "reboot": "restart",
    "reset": "restart",
    "reload": "restart",
    "restart system": "restart",
    "dobara chalu karo": "restart",     # hinglish: start again

    "lock": "lock_screen",
    "lock screen": "lock_screen",
    "lock up": "lock_screen",
    "secure": "lock_screen",
    "band karo screen": "lock_screen",  # hinglish

    "sleep": "sleep",
    "suspend": "sleep",
    "standby": "sleep",
    "rest": "sleep",
    "so ja": "sleep",                   # hinglish: go to sleep

    "hibernate": "hibernate",
    "deep sleep": "hibernate",

    "refresh": "refresh",
    "reload page": "refresh",

    # navigation — open a url or website
    "go": "open_url",
    "navigate": "open_url",
    "browse": "open_url",
    "visit": "open_url",
    "open site": "open_url",
    "open website": "open_url",
    "take me to": "open_url",
    "head to": "open_url",
    "jao": "open_url",                  # hinglish: go

    # web search
    "search": "search",
    "find": "search",
    "look up": "search",
    "look for": "search",
    "google": "search",
    "check": "search",
    "query": "search",
    "dhundo": "search",                 # hinglish: search/find
    "khojo": "search",

    # update mode — edit an existing mode's configuration
    "update": "update_mode",
    "edit": "update_mode",
    "modify": "update_mode",
    "change mode": "update_mode",
    "rename mode": "update_mode",

    # window management
    "focus": "focus_window",
    "bring": "focus_window",
    "foreground": "focus_window",
    "switch to": "focus_window",
    "go to": "focus_window",
    "jump to": "focus_window",

    "maximize": "maximize_window",
    "fullscreen": "maximize_window",
    "full screen": "maximize_window",
    "expand": "maximize_window",
    "full size": "maximize_window",

    "minimize": "minimize_window",
    "shrink": "minimize_window",
    "collapse": "minimize_window",
    "hide window": "minimize_window",
    "send to taskbar": "minimize_window",

    "show": "show_window",
    "unhide": "show_window",
    "restore": "show_window",
    "bring back": "show_window",

    "hide": "hide_window",
    "conceal": "hide_window",

    # snap/pin a window to a screen region
    "snap": "snap_window",
    "pin": "snap_window",
    "dock": "snap_window",
    "tile": "snap_window",

    "resize": "resize_window",
    "rescale": "resize_window",
    "scale": "resize_window",

    "move": "move_window",
    "reposition": "move_window",
    "shift": "move_window",

    # reminders and scheduling
    "remind": "set_reminder",
    "reminder": "set_reminder",
    "alert": "set_reminder",
    "notify": "set_reminder",
    "ping": "set_reminder",
    "warn": "set_reminder",

    "schedule": "schedule_task",
    "plan": "schedule_task",
    "book": "schedule_task",
    "set up": "schedule_task",
    "queue": "schedule_task",

    # add/create a task or note
    "add": "add_task",
    "create": "add_task",
    "make": "add_task",
    "new": "add_task",
    "note": "add_task",
    "jot": "add_task",
    "log": "add_task",

    # cancel/delete a task
    "cancel": "cancel_task",
    "delete": "cancel_task",
    "remove": "cancel_task",
    "clear": "cancel_task",
    "drop": "cancel_task",
    "dismiss": "cancel_task",
    "discard": "cancel_task",

    # file/app actions
    "copy": "copy_item",
    "duplicate": "copy_item",

    "rename": "rename_item",
    "relabel": "rename_item",

    "uninstall": "uninstall_app",
    "remove app": "uninstall_app",
    "delete app": "uninstall_app",

    # Phase 3 utilities
    "screenshot": "take_screenshot",
    "capture screen": "take_screenshot",
    "check disk": "check_disk_space",
    "disk space": "check_disk_space",
    "check internet": "check_internet",
    "empty": "empty_recycle_bin",
    "show clipboard": "show_clipboard_history",
    "clipboard history": "show_clipboard_history",
    "snippet": "expand_snippet",
    "expand snippet": "expand_snippet",
    "start pomodoro": "start_pomodoro",
    "stop pomodoro": "stop_pomodoro",

    # Phase 4 — mode field setters (typed shorthand for the config-editable-only
    # fields from Phase 3); phrased "<mode name> mode <field> <value>" so the
    # field keyword is never the first token — see mode_field_* shape functions
    "script": "set_mode_script",
    "vol": "set_mode_volume",
    "theme": "set_mode_theme",
    "layout": "capture_mode_layout",

    # Phase 4 — custom aliases
    "alias": "add_alias",

    # Phase 4 — comfort
    "undo": "undo_last_action",
    "help": "show_help",
    "cheatsheet": "show_help",
    "commands": "show_help",

    # Phase 5 — issue reporting & updates. Two-word keys only (never a bare
    # "install"/"apply"/"report"/"send") so these can't shadow any existing
    # one-word verb or misfire on an unrelated sentence that happens to start
    # with one of those words.
    "check updates": "check_for_updates",
    "install update": "apply_update",
    "apply update": "apply_update",
    "report issue": "report_issue",
    "report bug": "report_issue",
    "send report": "send_report",

    # Cycle 4 F1 — website allow-list. "allow" isn't otherwise a verb, so the
    # bare form is safe; "show allow list" is a three-word key so it wins over
    # the one-word "show" (show_window) via longest-phrase matching.
    "allow": "add_allow_site",
    "allow website": "add_allow_site",
    "allow site": "add_allow_site",
    "disallow": "remove_allow_site",
    "block website": "remove_allow_site",
    "block site": "remove_allow_site",
    "show allow list": "show_allow_list",
    "show allowed websites": "show_allow_list",

    # Cycle 4 F5 — reminders management
    "show reminders": "show_reminders",
    "list reminders": "show_reminders",

    # Cycle 4 F6 — named scripts. Two-word keys only ("save"/"run"/"delete"
    # are all existing one-word verbs); bare "run <name>" reaches run_script
    # via the resolver when <name> is a saved script.
    "save script": "save_script",
    "run script": "run_script",
    "delete script": "delete_script",
    "remove script": "delete_script",
    "show scripts": "show_scripts",
    "list scripts": "show_scripts",
}

# mode mapping
# maps intermediate app actions to their mode equivalents
# used by resolve_mode() when "mode" is detected in the token list
MODE_ACTION_MAP = {
    "open_app":     "activate_mode",
    "close_app":    "deactivate_mode",
    "add_task":     "create_mode",
    "cancel_task":  "delete_mode",
    "update_mode":  "update_mode",
} 

# synonyms mapped to valid targets in the system 
SYSTEM_TARGETS = {
    # brightness
    "brightness": "brightness",
    "screen": "brightness",
    "display": "brightness",
    "backlight": "brightness",

    # volume
    "volume": "volume",
    "sound": "volume",
    "audio": "volume",
    "speaker": "volume",
    "speakers": "volume",
    "music": "volume",

    # connectivity
    "wifi": "wifi",
    "wi-fi": "wifi",
    "wireless": "wifi",
    "internet": "wifi",
    "network": "wifi",
    "bluetooth": "bluetooth",
    "bt": "bluetooth",

    # power states
    "airplane mode": "airplane_mode",
    "flight mode": "airplane_mode",
    "do not disturb": "do_not_disturb",
    "dnd": "do_not_disturb",
    "night light": "night_light",
    "night mode": "night_light",
    "dark mode": "dark_mode",
    "light mode": "light_mode",

    # system
    "battery": "battery",
    "power": "power",
    "performance": "performance",
    "cpu": "cpu",
    "ram": "ram",
    "memory": "ram",
    "disk": "disk",
    "storage": "disk",
}

# tokens determining direction
DIRECTION_TOKENS = {
    # cardinal
    "left", "right", "top", "bottom",

    # descriptive equivalents
    "center", "centre", "middle",

    # corner positions
    "top-left", "top-right", "bottom-left", "bottom-right",
    "topleft", "topright", "bottomleft", "bottomright",

    # screen halves (natural language)
    "left half", "right half", "top half", "bottom half",

    # screen thirds
    "left third", "right third", "center third", "middle third",

    # screen quarters
    "top left", "top right", "bottom left", "bottom right",

    # fill/max synonyms (treated as direction for snap)
    "full", "fullscreen", "maximize", "max",
}

# indicators of a possible time token ahead
TIME_ANCHORS = {"at", "in", "on", "by", "before", "after", "every"}

# valid time units
TIME_UNITS = {
    "second", "seconds", "sec", "secs",
    "minute", "minutes", "min", "mins",
    "hour", "hours", "hr", "hrs",
    "morning", "afternoon", "evening", "night",
    "today", "tomorrow", "yesterday",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "daily", "weekly", "monthly",
}

# time-matching pattern for different strings
# shape 1: integer + am/pm (e.g. 5pm, 9am)
# shape 2: integer:integer + optional am/pm (e.g. 17:00, 5:30pm)
TIME_VALUE_PATTERN = re.compile(r"^\d+:\d+(?:am|pm)?$|^\d+(?:am|pm)$")

# mode update sub-action words
# signals that the following tokens should be added to the mode's app list
MODE_ADD_WORDS = {
    "add", "include", "plus",
    "jodo", "shamil karo",          # hinglish: add/include
}

# signals that the following tokens should be removed from the mode's app list
MODE_REMOVE_WORDS = {
    "remove", "without", "exclude", "except", "drop", "delete",
    "hatao", "nikalo",              # hinglish: remove/take out
}

# tokens that connect a list of applications
MODE_LIST_CONNECTORS = {"and", "also", "or"}

# ambiguous verbs 
# not clear what exactly are they talking about; could mean >1 thing
# these verbs require looking at the following target token to resolve the correct action
AMBIGUOUS_VERBS = {
    # set family
    "set", "put", "change", "adjust", "configure", "fix", "assign",
    "karo", "kar", "laga", "lagao", "rakh", "rakho",

    # create family
    "create", "make", "new", "add", "note", "jot", "log",

    # delete family
    "delete", "remove", "clear", "drop", "dismiss", "discard", "cancel",

    # enable family
    "turn on", "enable", "switch on",

    # disable family
    "turn off", "disable", "switch off",

    # switch family
    "switch", "toggle", "flip", "swap",
}

# finding the next target for ambiguous verb
# mapping it to proper action name
# key: (verb, target) tuple → value: resolved action string
VERB_TARGET_ACTION_MAP = {
    # set + system target → set_value
    ("set", "brightness"):      "set_value",
    ("set", "volume"):          "set_value",
    ("set", "sound"):           "set_value",
    ("set", "audio"):           "set_value",
    ("set", "wifi"):            "set_value",
    ("set", "bluetooth"):       "set_value",
    ("set", "display"):         "set_value",
    ("set", "screen"):          "set_value",
    ("set", "backlight"):       "set_value",
    ("set", "performance"):     "set_value",
    ("set", "power"):           "set_value",

    # set + task domain
    ("set", "reminder"):        "set_reminder",
    ("set", "alarm"):           "set_reminder",
    ("set", "alert"):           "set_reminder",
    ("set", "timer"):           "set_reminder",
    ("set", "task"):            "schedule_task",
    ("set", "schedule"):        "schedule_task",
    ("set", "meeting"):         "schedule_task",
    ("set", "event"):           "schedule_task",

    # set + mode domain
    ("set", "mode"):            "activate_mode",

    # create/make + task domain
    ("create", "reminder"):     "set_reminder",
    ("create", "alarm"):        "set_reminder",
    ("create", "alert"):        "set_reminder",
    ("create", "timer"):        "set_reminder",
    ("create", "task"):         "add_task",
    ("create", "todo"):         "add_task",
    ("create", "note"):         "add_task",
    ("create", "event"):        "schedule_task",
    ("create", "meeting"):      "schedule_task",
    ("create", "schedule"):     "schedule_task",

    # create/make + mode domain
    ("create", "mode"):         "create_mode",
    ("make", "mode"):           "create_mode",
    ("make", "reminder"):       "set_reminder",
    ("make", "alarm"):          "set_reminder",
    ("make", "task"):           "add_task",
    ("make", "todo"):           "add_task",
    ("make", "note"):           "add_task",
    ("make", "event"):          "schedule_task",

    # add + domain
    ("add", "task"):            "add_task",
    ("add", "todo"):            "add_task",
    ("add", "note"):            "add_task",
    ("add", "reminder"):        "set_reminder",
    ("add", "alarm"):           "set_reminder",
    ("add", "event"):           "schedule_task",
    ("add", "meeting"):         "schedule_task",
    ("add", "mode"):            "create_mode",

    # note/jot/log
    ("note", "task"):           "add_task",
    ("note", "reminder"):       "set_reminder",
    ("jot", "task"):            "add_task",
    ("jot", "reminder"):        "set_reminder",
    ("log", "task"):            "add_task",
    ("log", "reminder"):        "set_reminder",

    # delete/remove + domain
    ("delete", "mode"):         "delete_mode",
    ("delete", "reminder"):     "cancel_task",
    ("delete", "alarm"):        "cancel_task",
    ("delete", "task"):         "cancel_task",
    ("delete", "todo"):         "cancel_task",
    ("delete", "event"):        "cancel_task",
    ("delete", "app"):          "uninstall_app",
    ("remove", "mode"):         "delete_mode",
    ("remove", "reminder"):     "cancel_task",
    ("remove", "alarm"):        "cancel_task",
    ("remove", "task"):         "cancel_task",
    ("remove", "app"):          "uninstall_app",
    ("clear", "reminder"):      "cancel_task",
    ("clear", "alarm"):         "cancel_task",
    ("clear", "task"):          "cancel_task",
    ("cancel", "reminder"):     "cancel_task",
    ("cancel", "alarm"):        "cancel_task",
    ("cancel", "task"):         "cancel_task",
    ("cancel", "event"):        "cancel_task",
    ("cancel", "meeting"):      "cancel_task",
    ("dismiss", "reminder"):    "cancel_task",
    ("dismiss", "alarm"):       "cancel_task",
    ("drop", "task"):           "cancel_task",
    ("drop", "reminder"):       "cancel_task",
    ("discard", "task"):        "cancel_task",
    ("discard", "reminder"):    "cancel_task",

    # turn on + system target → set_value
    # (audit, Phase 5: added "dnd"/"network"/"bt"/"backlight" — previously
    # missing single-word targets meant these fell through to the bare
    # "turn on"/"turn off" VERB_ACTION_MAP entries instead, e.g. "turn off
    # dnd" resolved to a full system shutdown instead of toggling DND)
    ("turn on", "wifi"):        "set_value",
    ("turn on", "bluetooth"):   "set_value",
    ("turn on", "internet"):    "set_value",
    ("turn on", "wireless"):    "set_value",
    ("turn on", "network"):     "set_value",
    ("turn on", "bt"):          "set_value",
    ("turn on", "hotspot"):     "set_value",
    ("turn on", "sound"):       "unmute_volume",
    ("turn on", "audio"):       "unmute_volume",
    ("turn on", "volume"):      "unmute_volume",
    ("turn on", "display"):     "set_value",
    ("turn on", "screen"):      "set_value",
    ("turn on", "backlight"):   "set_value",
    ("turn on", "night"):       "set_value",
    ("turn on", "dark"):        "set_value",
    ("turn on", "dnd"):         "set_value",

    # turn on + mode domain
    ("turn on", "mode"):        "activate_mode",

    # turn off + system target → set_value
    ("turn off", "wifi"):       "set_value",
    ("turn off", "bluetooth"):  "set_value",
    ("turn off", "internet"):   "set_value",
    ("turn off", "wireless"):   "set_value",
    ("turn off", "network"):    "set_value",
    ("turn off", "bt"):         "set_value",
    ("turn off", "hotspot"):    "set_value",
    ("turn off", "sound"):      "mute_volume",
    ("turn off", "audio"):      "mute_volume",
    ("turn off", "volume"):     "mute_volume",
    ("turn off", "display"):    "set_value",
    ("turn off", "screen"):     "set_value",
    ("turn off", "backlight"):  "set_value",
    ("turn off", "night"):      "set_value",
    ("turn off", "dark"):       "set_value",
    ("turn off", "dnd"):        "set_value",

    # turn off + mode domain
    ("turn off", "mode"):       "deactivate_mode",

    # switch on/off + system target — mirrors turn on/off (audit, Phase 5:
    # previously had zero entries, so every "switch off <anything>" fell
    # through to the bare "switch off" → shutdown VERB_ACTION_MAP entry)
    ("switch on", "wifi"):       "set_value",
    ("switch on", "bluetooth"):  "set_value",
    ("switch on", "internet"):   "set_value",
    ("switch on", "wireless"):   "set_value",
    ("switch on", "network"):    "set_value",
    ("switch on", "bt"):         "set_value",
    ("switch on", "hotspot"):    "set_value",
    ("switch on", "sound"):      "unmute_volume",
    ("switch on", "audio"):      "unmute_volume",
    ("switch on", "volume"):     "unmute_volume",
    ("switch on", "display"):    "set_value",
    ("switch on", "screen"):     "set_value",
    ("switch on", "dnd"):        "set_value",
    ("switch on", "mode"):       "activate_mode",

    ("switch off", "wifi"):      "set_value",
    ("switch off", "bluetooth"): "set_value",
    ("switch off", "internet"):  "set_value",
    ("switch off", "wireless"):  "set_value",
    ("switch off", "network"):   "set_value",
    ("switch off", "bt"):        "set_value",
    ("switch off", "hotspot"):   "set_value",
    ("switch off", "sound"):     "mute_volume",
    ("switch off", "audio"):     "mute_volume",
    ("switch off", "volume"):    "mute_volume",
    ("switch off", "display"):   "set_value",
    ("switch off", "screen"):    "set_value",
    ("switch off", "dnd"):       "set_value",
    ("switch off", "mode"):      "deactivate_mode",

    # enable/disable + system target
    ("enable", "wifi"):         "set_value",
    ("enable", "bluetooth"):    "set_value",
    ("enable", "internet"):     "set_value",
    ("enable", "wireless"):     "set_value",
    ("enable", "hotspot"):      "set_value",
    ("enable", "mode"):         "activate_mode",
    ("disable", "wifi"):        "set_value",
    ("disable", "bluetooth"):   "set_value",
    ("disable", "internet"):    "set_value",
    ("disable", "wireless"):    "set_value",
    ("disable", "hotspot"):     "set_value",
    ("disable", "mode"):        "deactivate_mode",

    # switch/toggle + system target
    ("switch", "mode"):         "activate_mode",
    ("toggle", "wifi"):         "toggle_value",
    ("toggle", "bluetooth"):    "toggle_value",
    ("toggle", "sound"):        "toggle_value",
    ("toggle", "volume"):       "toggle_value",
    ("toggle", "display"):      "toggle_value",
    ("toggle", "mode"):         "activate_mode",
    ("flip", "wifi"):           "toggle_value",
    ("flip", "bluetooth"):      "toggle_value",
    ("flip", "mode"):           "activate_mode",

    # clear + clipboard domain (Phase 3 utility)
    ("clear", "clipboard"):     "clear_clipboard_history",

    # remove + alias domain (Phase 4)
    ("remove", "alias"):        "remove_alias",
    ("delete", "alias"):        "remove_alias",
}

# ---------------------------------------------------------------------------------------

# mode check and appropriate action function
# if "mode" is present in tokens and the action is ambiguous between app/mode,
# this upgrades the action to its mode-specific equivalent
def resolve_mode(action: str, tokens: list) -> str:
    if "mode" in tokens and action in MODE_ACTION_MAP:
        return MODE_ACTION_MAP[action]
    return action

# ---------------------------------------------------------------------------------------
# shape functions
# each function handles a specific command shape and builds the appropriate CommandIR
# all receive the full token list and the resolved action string

# standalone action; no target needed
# e.g. "mute", "shutdown", "sleep"
def verb_only(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)    # pass action, rest stays same
    return commandir_obj

# no dictionary target. could be anything, e.g., app name, url, website name
# collects all tokens that are not skip words, verbs, system targets, or integers
def free_target(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)

    # finding the free target word (for which no dictionary search exists)
    free_words_list = [] # an empty list that will contain all the free words present in the command input

    # looping through the whole list
    for token in tokens:

        # skip any filler words
        if token in SKIP_WORDS:
            continue
        # skip any verb words
        elif token in VERB_ACTION_MAP:
            continue
        # skip any system_target words
        elif token in SYSTEM_TARGETS:
            continue
        # skip any integers
        elif isinstance(token, int):
            continue
        # if none of these, then a free word
        else:
            free_words_list.append(token)

    # error reporting: no target found
    if not free_words_list:
        commandir_obj.errors.append("No Target Found!")
    else:
        # combining all the free words into a string
        commandir_obj.target = " ".join(free_words_list)

    return commandir_obj

# like free_target, but an empty target isn't an error — used where the target
# is genuinely optional (e.g. "start pomodoro" with no mode tied to it)
def optional_free_target(tokens: list, action: str) -> CommandIR:
    commandir_obj = free_target(tokens, action)
    if commandir_obj.target is None and commandir_obj.errors == ["No Target Found!"]:
        commandir_obj.errors = []
    return commandir_obj


# a system action, which will have a particular target and a number (as parameter)
# e.g. "increase brightness to 70", "set volume 50"
def system_target_number(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)

    # flags to check for error
    found_target = False
    found_level = False

    # finding target and parameter
    for token in tokens:

        # skip if a filler word
        if token in SKIP_WORDS:
            continue

        # check for target
        if token in SYSTEM_TARGETS:
            commandir_obj.target = SYSTEM_TARGETS[token]
            found_target = True

        # checking for level
        if isinstance(token, int):
            commandir_obj.params["level"] = token
            found_level = True

        # break if target and level found
        if found_target and found_level:
            break
    
    # -----------------------------------------------------------------------------------

    # if target not found, throw error
    if not found_target:
        commandir_obj.errors.append("No Target Found!")

    # if level not found, throw a warning (since it is easily correctable)
    if not found_level:
        commandir_obj.warnings.append("No Level Found!")

    return commandir_obj

# command with a free target (e.g. window/app name) and a direction
# e.g. "snap chrome to the left", "move notepad top right"
def free_target_direction(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)

    # finding the free target word (for which no dictionary search exists)
    free_words_list = [] # an empty list that will contain all the free words present in the command input
    direction = ""      # empty direction word

    # looping through the whole list
    i = 0
    while i < len(tokens):
        token = tokens[i]       # element

        # checking for two-word direction-based tokens (e.g. "top left", "bottom right")
        # must come before single-word checks to avoid partial matching
        if i+1 < len(tokens) and token + " " + str(tokens[i+1]) in DIRECTION_TOKENS:
            direction = token + " " + str(tokens[i+1])
            i += 2          # skip both tokens since they form one direction
        
        # skip any filler words
        elif token in SKIP_WORDS:
            i += 1
            continue

        # skip any verb words
        elif token in VERB_ACTION_MAP:
            i += 1
            continue
        
        # skip any system_target words
        elif token in SYSTEM_TARGETS:
            i += 1
            continue

        # skip any integers
        elif isinstance(token, int):
            i += 1
            continue

        # checking for one-word direction-based tokens (e.g. "left", "center")
        elif token in DIRECTION_TOKENS:
            direction = token
            i += 1

        # if none of these, then a free word (part of target)
        else:
            free_words_list.append(token)
            i += 1

    # error reporting: no target found
    if not free_words_list:
        commandir_obj.errors.append("No Target Found!")
    else:
        # combining all the free words into a string
        commandir_obj.target = " ".join(free_words_list)

    # error reporting: no direction found (warning since executor can use a default)
    if not direction:
        commandir_obj.warnings.append("No Direction Found!")
    else:
        commandir_obj.params["direction"] = direction

    return commandir_obj

# command with a free target (e.g. reminder subject) and a time component
# e.g. "remind me to call mom at 5pm", "set reminder for meeting in 20 minutes"
# time can appear before or after the target — classification is done by token type, not position
def free_target_time(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)

    time = []       # empty time list for accumulating different time values
    free_target_list = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # time value pattern match (e.g. "5pm", "17:00", "9:30am")
        if isinstance(token, str) and TIME_VALUE_PATTERN.match(token):
            time.append(token)
            i += 1

        # time anchor detected — look ahead for time unit or integer + unit
        elif token in TIME_ANCHORS:
            # anchor + unit (e.g. "on monday", "at morning")
            if i+1 < len(tokens) and tokens[i+1] in TIME_UNITS:
                time.append(token)
                time.append(tokens[i+1])
                i += 2
            # anchor + integer + unit (e.g. "in 20 minutes", "by 3 hours")
            elif i+1 < len(tokens) and isinstance(tokens[i+1], int) and i+2 < len(tokens) and tokens[i+2] in TIME_UNITS:
                time.append(token)
                time.append(tokens[i+1])
                time.append(tokens[i+2])
                i += 3
            # anchor with no recognizable time following — skip it
            else:
                i += 1
                
        # standalone time unit without anchor (e.g. "tomorrow", "friday")
        elif token in TIME_UNITS:
            time.append(token)
            i += 1

        # skip verbs, filler words, system targets, and raw integers
        elif token in SKIP_WORDS or token in VERB_ACTION_MAP or token in SYSTEM_TARGETS or isinstance(token, int):
            i += 1
        
        # anything else is part of the free target (reminder subject)
        else:
            free_target_list.append(token)
            i += 1
    
    # warning (not error) since a reminder without a time can still be stored
    if not time:
        commandir_obj.warnings.append("No Time Provided!")
    else:
        commandir_obj.params["time"] = time

    # error: a reminder with no subject is not actionable
    if not free_target_list:
        commandir_obj.errors.append("No Target Provided!")
    else:
        commandir_obj.target = " ".join(free_target_list)

    return commandir_obj

# command for creating or updating a named mode with an associated app list
# create_mode: extracts mode name + list of apps to open
# update_mode: extracts mode name + apps to add + apps to remove
def mode_with_apps(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)

    i = 0
    mode_target_found = False   # flag: have we identified the mode name yet?
    while i < len(tokens):
        token = tokens[i]

        # "mode" keyword signals the token immediately before it is the mode name
        # e.g. "create study mode" → target = "study"
        if token == "mode":
            if i-1 >= 0 and tokens[i-1] not in SKIP_WORDS and tokens[i-1] not in VERB_ACTION_MAP:
                commandir_obj.target = tokens[i-1]
                mode_target_found = True
            else:
                # error reporting: no mode name
                commandir_obj.errors.append("No Mode Name Provided!")
            i += 1

        # update_mode: scan for add/remove boundaries and collect app lists accordingly
        elif action == "update_mode":

            # add boundary hit — collect all following tokens as apps to add
            # stop when a remove boundary or another add boundary is encountered
            if token in MODE_ADD_WORDS:
                commandir_obj.params["add"] = []
                j = i + 1
                while j < len(tokens) and tokens[j] not in MODE_REMOVE_WORDS and tokens[j] not in MODE_ADD_WORDS:
                    if tokens[j] not in SKIP_WORDS and tokens[j] not in MODE_LIST_CONNECTORS:
                        commandir_obj.params["add"].append(tokens[j])
                    j += 1

                if not commandir_obj.params["add"]:
                    commandir_obj.errors.append("No Adding Targets Provided!")

                i = j   # jump outer loop past all consumed tokens
            
            # remove boundary hit — collect all following tokens as apps to remove
            # stop when an add boundary or another remove boundary is encountered
            elif token in MODE_REMOVE_WORDS:
                commandir_obj.params["remove"] = []
                j = i + 1
                while j < len(tokens) and tokens[j] not in MODE_ADD_WORDS and tokens[j] not in MODE_REMOVE_WORDS:
                    if tokens[j] not in SKIP_WORDS and tokens[j] not in MODE_LIST_CONNECTORS:
                        commandir_obj.params["remove"].append(tokens[j])
                    j += 1

                if not commandir_obj.params["remove"]:
                    commandir_obj.errors.append("No Removing Targets Provided!")

                i = j   # jump outer loop past all consumed tokens

            # token is neither add nor remove boundary — skip (e.g. verb, mode name already captured)
            else:
                i += 1

        # create_mode: once mode name is found, collect all remaining tokens as the new app list
        # skips verbs, filler words, and mode boundary words
        elif action == "create_mode" and mode_target_found:
            commandir_obj.params["new"] = []

            while i < len(tokens):
                token = tokens[i]
                if token not in SKIP_WORDS and token not in VERB_ACTION_MAP and token not in MODE_ADD_WORDS and token not in MODE_REMOVE_WORDS and token not in MODE_LIST_CONNECTORS:
                    commandir_obj.params["new"].append(token)
                i += 1

        # token doesn't match any condition — advance (handles pre-mode-name tokens)
        else:
            i += 1

    return commandir_obj

# ---------------------------------------------------------------------------------------
# Phase 4 shape functions — mode field setters
#
# Phrasing is "<mode name> mode <field> <value...>" (e.g. "gaming mode script
# steam.exe", "gaming mode vol 40", "gaming mode theme dark", "gaming mode
# layout"). The mode name comes *before* "mode" (same convention as
# create/update mode), and the field keyword comes right after it — this
# keeps every field keyword safely out of first-token position, so adding
# them to VERB_ACTION_MAP can't shadow an existing one-word verb.

def _mode_name_before(tokens: list) -> str:
    if "mode" not in tokens:
        return None
    idx = tokens.index("mode")
    if idx - 1 >= 0 and tokens[idx - 1] not in SKIP_WORDS and tokens[idx - 1] not in VERB_ACTION_MAP:
        return str(tokens[idx - 1])
    return None


def mode_set_script(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    name = _mode_name_before(tokens)
    if not name:
        commandir_obj.errors.append("No Mode Name Provided!")
        return commandir_obj
    commandir_obj.target = name

    # Bug fix (audit, Phase 5): the field keyword ("script"/"vol"/"theme") is
    # itself the matched verb for this action, so command_parser's main loop
    # already strips it out of `tokens` before calling this function — it's
    # never present here. Everything from right after "mode" onward is the
    # script command directly (no extra "+1" to skip past a keyword that's
    # already gone).
    idx = tokens.index("mode") + 1
    remaining = [str(t) for t in tokens[idx:] if t not in SKIP_WORDS]
    if not remaining:
        commandir_obj.errors.append("No Script Command Provided!")
    else:
        commandir_obj.params["script"] = " ".join(remaining)
    return commandir_obj


def mode_set_volume(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    name = _mode_name_before(tokens)
    if not name:
        commandir_obj.errors.append("No Mode Name Provided!")
        return commandir_obj
    commandir_obj.target = name

    # "vol" (the field keyword/verb) is already stripped — see mode_set_script.
    idx = tokens.index("mode") + 1
    level = next((t for t in tokens[idx:] if isinstance(t, int)), None)
    if level is None:
        commandir_obj.errors.append("No Volume Level Provided!")
    else:
        commandir_obj.params["level"] = level
    return commandir_obj


def mode_set_theme(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    name = _mode_name_before(tokens)
    if not name:
        commandir_obj.errors.append("No Mode Name Provided!")
        return commandir_obj
    commandir_obj.target = name

    # "theme" (the field keyword/verb) is already stripped — see mode_set_script.
    idx = tokens.index("mode") + 1
    theme = next((t for t in tokens[idx:] if t in ("dark", "light")), None)
    if theme is None:
        commandir_obj.errors.append("No Theme (dark/light) Provided!")
    else:
        commandir_obj.params["theme"] = theme
    return commandir_obj


def mode_capture_layout(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    name = _mode_name_before(tokens)
    if not name:
        commandir_obj.errors.append("No Mode Name Provided!")
        return commandir_obj
    commandir_obj.target = name
    return commandir_obj


# ---------------------------------------------------------------------------------------
# Phase 4 shape functions — custom aliases
# "alias browser as chrome" -> user word "browser" maps to canonical "chrome"

def alias_pair(tokens: list, action: str) -> CommandIR:
    # "alias" is itself the matched verb for this action, so command_parser's
    # main loop has already stripped it out of `tokens` before calling here —
    # everything left (minus filler words) is [alias_word, ...target_words].
    commandir_obj = CommandIR(action=action)
    rest = [str(t) for t in tokens if t not in SKIP_WORDS]
    if len(rest) < 2:
        commandir_obj.errors.append("Need both an alias word and its target (e.g. 'alias browser as chrome').")
        return commandir_obj

    commandir_obj.params["alias"] = rest[0]
    commandir_obj.target = " ".join(rest[1:])
    return commandir_obj


def alias_only_target(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    free = [str(t) for t in tokens if t not in SKIP_WORDS and t not in VERB_ACTION_MAP and t != "alias" and not isinstance(t, int)]
    if not free:
        commandir_obj.errors.append("No Target Found!")
    else:
        commandir_obj.target = " ".join(free)
    return commandir_obj


# Phase 5 — "report issue <optional free-text description>". The description
# is genuinely optional (an empty one just means "no extra details"), so this
# never appends a "No Target Found!" error the way free_target would. The verb
# match consumes the whole "report issue"/"report bug" phrase (both words),
# so nothing left in `tokens` needs a marker search — it's all description.
def report_issue_shape(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    remaining = [str(t) for t in tokens if t not in SKIP_WORDS]
    if remaining:
        commandir_obj.params["description"] = " ".join(remaining)
    return commandir_obj


# Cycle 4 F6 — "save script <name> as <command...>". The verb ("save script")
# is already stripped; the first remaining token is the name and everything
# after an optional "as" is the command, joined verbatim-as-tokenized (same
# shape pattern as add_alias). Nothing here ever runs the command.
def save_script_shape(tokens: list, action: str) -> CommandIR:
    commandir_obj = CommandIR(action=action)
    rest = [str(t) for t in tokens]
    if rest and rest[0] in SKIP_WORDS:
        rest = rest[1:]
    if len(rest) < 2:
        commandir_obj.errors.append(
            "Need a name and a command (e.g. 'save script backup as robocopy …').")
        return commandir_obj
    commandir_obj.params["name"] = rest[0]
    command_tokens = rest[1:]
    if command_tokens and command_tokens[0] == "as":
        command_tokens = command_tokens[1:]
    if not command_tokens:
        commandir_obj.errors.append("No command to save.")
        return commandir_obj
    commandir_obj.params["command"] = " ".join(command_tokens)
    return commandir_obj


# ---------------------------------------------------------------------------------------

# dispatch table: maps each resolved action to its shape function
# shape function determines how tokens are processed to build the CommandIR
ACTION_FUNCTION_MAP = {
    "open_app":             free_target,
    "close_app":            free_target,

    "increase_value":       system_target_number,
    "decrease_value":       system_target_number,
    "set_value":            system_target_number,
    "toggle_value":         system_target_number,

    "mute_volume":          verb_only,
    "unmute_volume":        verb_only,

    "shutdown":             verb_only,
    "restart":              verb_only,
    "lock_screen":          verb_only,
    "sleep":                verb_only,
    "hibernate":            verb_only,
    "refresh":              verb_only,

    "open_url":             free_target,
    "search":               free_target,

    "activate_mode":        free_target,
    "deactivate_mode":      free_target,
    "create_mode":          mode_with_apps,
    "delete_mode":          free_target,
    "update_mode":          mode_with_apps,

    "focus_window":         free_target,
    "maximize_window":      free_target,
    "minimize_window":      free_target,
    "show_window":          free_target,
    "hide_window":          free_target,
    "snap_window":          free_target_direction,
    "resize_window":        free_target_direction,
    "move_window":          free_target_direction,

    "set_reminder":         free_target_time,
    "schedule_task":        free_target_time,
    "add_task":             free_target,
    "cancel_task":          free_target,

    "copy_item":            free_target,
    "rename_item":          free_target,
    "uninstall_app":        free_target,

    "take_screenshot":         verb_only,
    "check_disk_space":        verb_only,
    "check_internet":          verb_only,
    "empty_recycle_bin":       verb_only,
    "show_clipboard_history":  verb_only,
    "clear_clipboard_history": verb_only,
    "expand_snippet":          free_target,
    "start_pomodoro":          optional_free_target,
    "stop_pomodoro":           verb_only,

    "set_mode_script":         mode_set_script,
    "set_mode_volume":         mode_set_volume,
    "set_mode_theme":          mode_set_theme,
    "capture_mode_layout":     mode_capture_layout,

    "add_alias":               alias_pair,
    "remove_alias":            alias_only_target,

    "undo_last_action":        verb_only,
    "show_help":               verb_only,

    "report_issue":            report_issue_shape,
    "send_report":             verb_only,
    "check_for_updates":       verb_only,
    "apply_update":            verb_only,

    # Cycle 4
    "add_allow_site":          free_target,
    "remove_allow_site":       free_target,
    "show_allow_list":         verb_only,
    "show_reminders":          verb_only,
    "save_script":             save_script_shape,
    "run_script":              free_target,
    "delete_script":           free_target,
    "show_scripts":            verb_only,
}

# ---------------------------------------------------------------------------------------

# Bug fix (audit, Phase 5): AMBIGUOUS_VERBS contains a few two-word entries
# ("turn on", "turn off", "switch on", "switch off"), but the original loop
# only ever checked a *single* token against that set — a two-word phrase can
# never equal one token, so those entries could never match. In practice that
# meant "turn on wifi" silently fell through to the plain VERB_ACTION_MAP
# lookup ("turn on" -> open_app, dropping "wifi"), and "turn off wifi"
# resolved to "turn off" -> shutdown — i.e. any "turn off <target>" sentence
# triggered a full system-shutdown confirmation instead of toggling the named
# target. This helper checks the two-word form first so it can never be
# shadowed by a coincidentally-mapped one-word prefix.
def _match_ambiguous_verb(tokens: list, i: int):
    """Returns (verb_key, target_idx) if tokens[i:] starts with a known
    ambiguous verb followed by a target token, else None. Tries the two-word
    form ("turn on", "switch off", ...) before the one-word form so it's
    never shadowed by it."""
    if i + 2 < len(tokens):
        two_word = str(tokens[i]) + " " + str(tokens[i + 1])
        if two_word in AMBIGUOUS_VERBS:
            return two_word, i + 2
    if tokens[i] in AMBIGUOUS_VERBS and i + 1 < len(tokens):
        return tokens[i], i + 1
    return None


# Bug fix (audit, Phase 5): VERB_ACTION_MAP has always held a handful of
# three-word keys (e.g. "shut down app", "send to taskbar", "take me to"),
# but the lookup only ever tried a two-word join — those keys were dead code,
# unreachable no matter what the user typed. Worse, "shut down app notepad"
# would match the two-word "shut down" -> shutdown before ever getting a
# chance at the (unreachable) three-word key, turning "close this one app"
# into a whole-system shutdown prompt. This helper tries the three-word form
# first, then two-word, then one-word, so a longer/more specific phrase is
# never shadowed by a shorter prefix that happens to also be mapped.
def _match_verb_action(tokens: list, i: int):
    """Returns (action, matched_len) for the longest VERB_ACTION_MAP phrase
    starting at position i, or None."""
    if i + 2 < len(tokens):
        three_word = str(tokens[i]) + " " + str(tokens[i + 1]) + " " + str(tokens[i + 2])
        if three_word in VERB_ACTION_MAP:
            return VERB_ACTION_MAP[three_word], 3
    if i + 1 < len(tokens):
        two_word = str(tokens[i]) + " " + str(tokens[i + 1])
        if two_word in VERB_ACTION_MAP:
            return VERB_ACTION_MAP[two_word], 2
    if tokens[i] in VERB_ACTION_MAP:
        return VERB_ACTION_MAP[tokens[i]], 1
    return None


# main command_parser function
# entry point for the parser stage
# receives a token list from the input processor and returns a populated CommandIR
def command_parser(tokens: list) -> list:

    # looping through the command token list to find out the verb
    for i, token in enumerate(tokens):

        # skip if an unimportant verb
        if token in SKIP_WORDS:
            continue

        # checking for ambiguous verb (one- or two-word) — needs the next
        # token (target) to determine the correct action
        ambiguous = _match_ambiguous_verb(tokens, i)
        if ambiguous is not None:
            verb_key, target_idx = ambiguous
            target_token = tokens[target_idx]

            # checking for existence in the verb+target combo
            if (verb_key, target_token) in VERB_TARGET_ACTION_MAP:
                action = VERB_TARGET_ACTION_MAP[(verb_key, target_token)]
                action = resolve_mode(action, tokens)
                consumed = str(verb_key).count(" ") + 1
                remaining = tokens[:i] + tokens[i + consumed:]
                return ACTION_FUNCTION_MAP[action](remaining, action)

            # verb+target combo not in map — fall back to treating verb as unambiguous
            fallback = _match_verb_action(tokens, i)
            if fallback is not None:
                action, consumed = fallback
                action = resolve_mode(action, tokens)
                remaining = tokens[:i] + tokens[i + consumed:]
                return ACTION_FUNCTION_MAP[action](remaining, action)

            # this token looked like an ambiguous verb but resolved to nothing usable —
            # move on and let a later token be checked instead of getting stuck here
            continue

        # unambiguous verb — resolve directly without needing target context
        # (tries three-word, then two-word, then one-word phrases)
        match = _match_verb_action(tokens, i)
        if match is not None:
            action, consumed = match
            action = resolve_mode(action, tokens)
            # Bug fix (audit, Phase 5): shape functions like free_target only
            # ever recognized a *whole* multi-word verb phrase as filterable
            # (via a single-token VERB_ACTION_MAP membership check), so the
            # individual words of a matched multi-word verb (e.g. "down" in
            # "close down", "to"/"taskbar" in "send to taskbar") used to leak
            # into the parsed target. Slicing out exactly the matched verb
            # span here — nothing more, nothing less — means every shape
            # function gets a clean target list without needing its own fix.
            remaining = tokens[:i] + tokens[i + consumed:]
            return ACTION_FUNCTION_MAP[action](remaining, action)

    # error handling: no verb/action found
    return CommandIR(errors=["No Action Found!"])  # report error

# ---------------------------------------------------------------------------------------