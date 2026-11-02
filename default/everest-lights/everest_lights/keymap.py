"""Linux evdev codes to AlienFX light ids for the x15 R2 keyboard.

Light ids come from the Alienware x15/17 R2 map in T-Troll's devices list.
Letter ids match the sibling Dell per-key maps, which put Space on id 105.
The nav cluster is labeled as a numpad in that file and as arrows on the x17 R1;
on this laptop those ids are the arrow, Home, End, and Delete keys.
"""

from __future__ import annotations

# evdev code -> one or more firmware light ids
KEY_LIGHTS: dict[int, tuple[int, ...]] = {
    1: (0,),  # ESC
    59: (1,),  # F1
    60: (2,),
    61: (3,),
    62: (4,),
    63: (5,),
    64: (6,),
    65: (7,),
    66: (8,),
    67: (9,),
    68: (10,),  # F10
    87: (11,),  # F11
    88: (12,),  # F12
    102: (13,),  # HOME
    107: (14,),  # END
    111: (15,),  # DELETE
    113: (16,),  # MUTE
    114: (17,),  # VOLUMEDOWN
    115: (18,),  # VOLUMEUP
    248: (19,),  # MICMUTE
    41: (20,),  # GRAVE
    2: (21,),  # 1
    3: (22,),
    4: (23,),
    5: (24,),
    6: (25,),
    7: (26,),
    8: (27,),
    9: (28,),
    10: (29,),
    11: (30,),  # 0
    12: (31,),  # MINUS
    13: (32,),  # EQUAL
    14: (34,),  # BACKSPACE
    15: (40,),  # TAB
    16: (42,),  # Q
    17: (43,),  # W
    18: (44,),
    19: (45,),
    20: (46,),
    21: (47,),
    22: (48,),
    23: (49,),
    24: (50,),
    25: (51,),  # P
    26: (52,),  # LEFTBRACE
    27: (53,),  # RIGHTBRACE
    43: (55,),  # BACKSLASH
    58: (60,),  # CAPSLOCK
    30: (62,),  # A
    31: (63,),
    32: (64,),
    33: (65,),
    34: (66,),
    35: (67,),
    36: (68,),
    37: (69,),
    38: (70,),  # L
    39: (71,),  # SEMICOLON
    40: (72,),  # APOSTROPHE
    28: (74,),  # ENTER
    42: (80,),  # LEFTSHIFT
    44: (83,),  # Z
    45: (84,),
    46: (85,),
    47: (86,),
    48: (87,),
    49: (88,),
    50: (89,),  # M
    51: (90,),  # COMMA
    52: (91,),  # DOT
    53: (92,),  # SLASH
    54: (94,),  # RIGHTSHIFT
    29: (100,),  # LEFTCTRL
    464: (101,),  # FN, when the firmware reports it
    125: (102,),  # LEFTMETA
    56: (104,),  # LEFTALT
    57: (105,),  # SPACE
    100: (111,),  # RIGHTALT
    97: (112,),  # RIGHTCTRL
    103: (114,),  # UP
    105: (133,),  # LEFT
    108: (134,),  # DOWN
    106: (135,),  # RIGHT
}

# Every id we paint so unmapped LEDs follow the resting color.
PAINTED_IDS = tuple(range(0, 136))


def lights_for(code: int) -> tuple[int, ...]:
    return KEY_LIGHTS.get(code, ())
