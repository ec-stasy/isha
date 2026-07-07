# regular expression used to identify a certain string pattern
import re

# numeric, word-based string conversion to respective int type
def numeric_str_to_int_conversion(input_tokens: list) -> list:
    """
    i/p: token list with 'minus', numeric word, string digit
    o/p: token list containing corresponding int types

    convert ALL types of numeric words and digits to int
    """

    # words with only one numeric word
    SINGLE_NUMERIC_WORDS = [
        "zero", "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen", 
        "hundred"
    ]

    # words MAY require two numeric words
    DOUBLE_NUMERIC_WORDS = [
        "twenty", "thirty", "forty", "fifty", 
        "sixty", "seventy", "eighty", "ninety",
    ]

    # str based numeric word -> int equivalent
    NUMERIC_WORD_MAP = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20,
        "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
        "hundred": 100,
        # doubles
        "twenty one": 21, "twenty two": 22, "twenty three": 23, "twenty four": 24,
        "twenty five": 25, "twenty six": 26, "twenty seven": 27, "twenty eight": 28,
        "twenty nine": 29,
        "thirty one": 31, "thirty two": 32, "thirty three": 33, "thirty four": 34,
        "thirty five": 35, "thirty six": 36, "thirty seven": 37, "thirty eight": 38,
        "thirty nine": 39,
        "forty one": 41, "forty two": 42, "forty three": 43, "forty four": 44,
        "forty five": 45, "forty six": 46, "forty seven": 47, "forty eight": 48,
        "forty nine": 49,
        "fifty one": 51, "fifty two": 52, "fifty three": 53, "fifty four": 54,
        "fifty five": 55, "fifty six": 56, "fifty seven": 57, "fifty eight": 58,
        "fifty nine": 59,
        "sixty one": 61, "sixty two": 62, "sixty three": 63, "sixty four": 64,
        "sixty five": 65, "sixty six": 66, "sixty seven": 67, "sixty eight": 68,
        "sixty nine": 69,
        "seventy one": 71, "seventy two": 72, "seventy three": 73, "seventy four": 74,
        "seventy five": 75, "seventy six": 76, "seventy seven": 77, "seventy eight": 78,
        "seventy nine": 79,
        "eighty one": 81, "eighty two": 82, "eighty three": 83, "eighty four": 84,
        "eighty five": 85, "eighty six": 86, "eighty seven": 87, "eighty eight": 88,
        "eighty nine": 89,
        "ninety one": 91, "ninety two": 92, "ninety three": 93, "ninety four": 94,
        "ninety five": 95, "ninety six": 96, "ninety seven": 97, "ninety eight": 98,
        "ninety nine": 99,
    }

    # copying list so that input is not modified
    # tokens = input_tokens (doesn't copy the actual list, instead makes 'tokens' point to the same)
    tokens = input_tokens.copy()      
    i = 0       # indexing
    while i < len(tokens):
        token = tokens[i]       # holds non-transformed value of an element

        # singular numeric word
        if token in SINGLE_NUMERIC_WORDS:
            tokens[i] = NUMERIC_WORD_MAP[token]
            # single word: direct conversion to numeric word
        
        # double numeric word
        if token in DOUBLE_NUMERIC_WORDS:
            if i+1 < len(tokens) and tokens[i+1] in SINGLE_NUMERIC_WORDS:
                tokens[i] = NUMERIC_WORD_MAP[token + " " + tokens[i+1]]     
                # transform the first word of the double-word into the respective int
                tokens.pop(i+1)     # remove the remaining numeric word part left
            else:
                tokens[i] = NUMERIC_WORD_MAP[token]     # a multiple of 10. hence, no following word. 

        # numeric digits as string: convert str -> int
        # only if token is still non-transformed and of str type
        # i.e., not an already int type
        if isinstance(token, str) and token.lstrip("-").isdigit():
            tokens[i] = int(token)

        # increment index
        i += 1   

    return tokens

# main input processor function
def input_processor(command_input: str) -> list:
    """
    i/p: a string containing user command input
    o/p: commands list containing tokens 

    1. normalize: lower-case
    2. remove punctuation marks, keeping only hyphen right before a digit (-1)
    3. normalize: strip front, end whitespaces
    4. listing into tokens
    5. numeric word/string: int conversion
    """
    # 1. normalize: lower-case
    command_input = command_input.lower()

    # 2. remove punctuation marks, keeping only hyphen right before a digit (-1)
    # and dots that sit directly between two word characters (e.g. "youtube.com"),
    # so bare domains survive tokenization instead of collapsing into one word
    # r"": treat as regex, \ are not be treated differently
    # [^\w\s.-]: delete everything except (^) words- letters, digits, _ (\w)
    #           & whitespaces (\s) & hyphen (-) & dot (.); exactly what characters
    # |: OR
    # -(?!\d): hyphen kept only when followed by a digit; lookahead conditions
    tokens = re.sub(r"[^\w\s.-]|-(?!\d)", "", command_input)

    # drop any dot that isn't sandwiched between two word characters — a
    # trailing sentence period or stray dot, not a domain separator
    tokens = re.sub(r"(?<!\w)\.|\.(?!\w)", "", tokens)

    # handling the 'minus' word issue
    tokens = re.sub(r"minus\s+(\d+)", r"-\1", tokens)
    # \s+ — consume the whitespace between "minus" and the number.
    # (\d+) — capture the digits that follow.
    # r"-\1" — replace the whole match with - followed by whatever was captured in group 1.

    # 3 & 4. normalize and listing
    tokens = tokens.strip().split()

    # 5. numeric word/digit_string to int conversion
    tokens = numeric_str_to_int_conversion(tokens)

    return tokens