# pcalc/theme.py
# Pan Devs color palette — based on the Pan Devs eye logo
# All colors are rich-compatible (hex strings or named colors)

PRIMARY   = "#6B7A3E"   # olive green   — banner, titles, primary elements
ACCENT    = "#a0854e"   # amber gold    — version, highlights, interactive elements
SUCCESS   = "#8A9A5B"   # sage green    — calc detected, install OK, update done
ERROR     = "red"       # rich red      — errors, failures
WARNING   = "yellow"    # rich yellow   — warnings, updates available
DIM       = "dim white" # secondary text, separators

# Rich style strings (ready to pass to console.print)
S_PRIMARY = f"bold {PRIMARY}"
S_ACCENT  = f"bold {ACCENT}"
S_SUCCESS = f"bold {SUCCESS}"
S_ERROR   = f"bold {ERROR}"
S_WARNING = f"bold {WARNING}"
S_DIM     = DIM