def listtopattern(plist):
    """Converts a list of strings to an 'or'-seperated regex pattern (includes word breaks at the ends)"""
    plist.sort(key=len, reverse=True)       # Sort so longest phrases are evaluated first (sub-phrases last)
    pattern = r'' + plist[0]
    if len(plist) != 1:
        for x in plist[1:]:
            pattern = pattern + '|' + x
    pattern = r'\b(' + pattern + r')\b'
    return pattern


def listtopatternraw(plist):
    """Converts a list of strings to an 'or'-seperated regex pattern """
    plist.sort(key=len, reverse=True)
    pattern = r'' + plist[0]
    if len(plist) != 1:
        for x in plist[1:]:
            pattern = pattern + '|' + x
    pattern = r'(' + pattern + r')'
    return pattern


def listtononcapture(plist):
    """Converts a list of strings to a non-capturing 'or'-seperated regex pattern"""
    plist.sort(key=len, reverse=True)
    pattern = r'' + plist[0]
    if len(plist) != 1:
        for x in plist[1:]:
            pattern = pattern + '|' + x
    pattern = r'(?:' + pattern + r')'
    return pattern
