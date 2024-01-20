import re

# searchInvoice takes a given regex and searches the line for a match
# params: line: str, text to be searched
# params: regex: str, regex to be matched
# returns: Either returns the str match of the regex if successful, or None
def searchLine(line, regex):
    res = re.search(regex, line)
    
    if res:
        return res.group()
    else:
        return None