"""Compression codecs: each module a `compress(data) -> bytes` and a decoder returning (data, bytes read).

Formats a chip fixes (S-DD1) and generic, parameterized ones. A game's own quirks (headers, size prefixes,
raw-or-compressed flags) stay in the game, on top of these.
"""
