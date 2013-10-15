__all__ = ['grouper', 'singleton', 'nowish_tz', 'aws']

# http://stackoverflow.com/questions/2348317/how-to-write-a-pager-for-python-iterators/2350904#2350904        
def grouper(iterable, page_size):
    page= []
    for item in iterable:
        page.append( item )
        if len(page) == page_size:
            yield page
            page= []
    if len(page) > 0:
        yield page

#http://stackoverflow.com/questions/42558/python-and-the-singleton-pattern/2752280#2752280
def singleton(cls):
    instances = {}
    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return getinstance

def nowish_tz():
    # put in Pacific time
    tz_PT = pytz.timezone("US/Pacific")
    return datetime.datetime(*datetime.datetime.utcnow().timetuple()[:6]).replace(tzinfo=pytz.utc).astimezone(tz_PT)