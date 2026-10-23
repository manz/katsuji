"""Compression codecs: each a `compress(data) -> bytes` and a decoder returning (data, bytes read), as module
functions (S-DD1) or methods of a format's parameter set (LZSS).

Formats a chip fixes (S-DD1) and generic, parameterized ones. A game's own quirks (headers, size prefixes,
raw-or-compressed flags) stay in the game, on top of these.
"""
