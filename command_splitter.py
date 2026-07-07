# the general starting verbs of a command
# as sets because finding answer is quicker and easier
COMMAND_VERBS = {
    # Open/Launch
    "open", "launch", "start", "run", "load",

    # Close/Kill
    "close", "quit", "exit", "kill", "stop",

    # System controls
    "set", "increase", "decrease", "raise", "lower",
    "turn", "enable", "disable", "toggle",
    "mute", "unmute", "adjust",

    # Brightness/Volume specific
    "dim", "brighten", "maximize", "minimize",

    # System actions
    "shutdown", "restart", "reboot", "lock", "sleep",
    "hibernate", "refresh",

    # File/App actions
    "search", "find", "show", "hide", "move",
    "copy", "delete", "rename", "create",

    # Browser/URL
    "go", "navigate", "browse", "play",

    # Mode management
    "activate", "deactivate", "switch",

    # Reminders/Scheduling
    "remind", "schedule", "add", "cancel",

    # Window management
    "focus", "bring", "snap", "resize",

    # Hinglish
    "khol", "band", "kar", "karo", "chalu",
    "chalao", "bund", "laga", "hatao",
}

# words differentiating between two commands
SINGLE_WORD_COMMAND_DELIMITERS = {
    "and",
    "then",
    "next",
    "also",

    # Hindi-English (Hinglish) — important for your user base
    "aur",
    "phir",
}

# multi-word Command Delimiter
TWO_WORD_COMMAND_DELIMITER = {
    # two word
    "as well",
    "and then",
    "and also",
    "after that",
    "once done",
    "when finished",
    "followed by",
    "uske baad",
    "aur phir",
}

# verbs whose sentences carry a mode's app/website list — "and" inside that list
# joins list items, not separate commands (e.g. "create study mode chrome and
# spotify" must not split into two commands at "and")
MODE_LIST_VERBS = {"create", "update", "make", "new", "add"}


def _is_mode_list_command(tokens: list) -> bool:
    return "mode" in tokens and any(verb in tokens for verb in MODE_LIST_VERBS)


# main command splitter function
def command_splitter(tokens: list) -> list:
    """
    i/p: token list of input command
    o/p: token list broken into multiple commands' lists
    """
    i = 0                   # indexing (manual for better skipping and leveling up)
    temp_tokens = []        # final multi-commands' lists' list
    temp_command = []       # current command list
    command_verb = None     # have we encountered any command verb yet or not...

    while i < len(tokens):
        token = tokens[i]   # element

        # two word delimiter check:
        # there exists a next word; the current + next word form a two word delimiter
        # there exists a next-to-next word; that word is a verb 
        # (while we have already found a verb!)
        if (i+1 < len(tokens) and (str(token) + " " + str(tokens[i+1])) in TWO_WORD_COMMAND_DELIMITER 
        and i+2 < len(tokens) and tokens[i+2] in COMMAND_VERBS and command_verb) and not _is_mode_list_command(tokens):
            temp_tokens.append(temp_command)        # append the current command to final multi-command token list
            temp_command = []       # reset current command
            command_verb = False    # reset command_verb found flag
            i += 2                  # skip through both delimiters and start fresh at the verb

        # same command with multiple targets (two-word delimiter)
        elif i+1 < len(tokens) and (str(token) + " " + str(tokens[i+1])) in TWO_WORD_COMMAND_DELIMITER and command_verb and i+2 < len(tokens) and tokens[i+2] not in COMMAND_VERBS and not _is_mode_list_command(tokens):
            temp_tokens.append(temp_command)    # add command list to final multi-command list
            temp_command = [command_verb]       # new command inherits the same verb
            i += 2                              # increment/skip the delimiters
            
        # single word delimiter check
        elif token in SINGLE_WORD_COMMAND_DELIMITERS and i+1 < len(tokens) and tokens[i+1] in COMMAND_VERBS and command_verb and not _is_mode_list_command(tokens):
            temp_tokens.append(temp_command)    # command list added to final tokens' list
            temp_command = []                   # one command found, searching for next
            command_verb = False                # command verb found flag updated to False
            i += 1                              # skip the delimiter word [0: delimiter, 1: verb]

        # same command with multiple targets (single word delimiter)
        elif token in SINGLE_WORD_COMMAND_DELIMITERS and command_verb and i+1 < len(tokens) and tokens[i+1] not in COMMAND_VERBS and not _is_mode_list_command(tokens):
            temp_tokens.append(temp_command)    # add command list to final multi-command list
            temp_command = [command_verb]       # new command inherits the same verb
            i += 1                              # increment

        # last word in the whole token list
        elif i == len(tokens) - 1:
            temp_command.append(token)
            temp_tokens.append(temp_command)
            i += 1

        # any word of a command without encountering a delimiter
        else:
            temp_command.append(token)          # generate list of the whole command's tokens
            
            # command-verb saved
            if token in COMMAND_VERBS:
                command_verb = token

            i += 1                              # increment
        
    return temp_tokens