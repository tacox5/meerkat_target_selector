import datetime
from dateutil import parser
from .logger import log as logger

def add_time(time, del_t):
    """Add time to the start of the observation to calculate the time this
       observation will take place

    Args:
        time: (str)
            String that is formatted like a datetime object
        del_t: (float)
            Seconds since the beginning of the observation

    Returns:
        obs_time: (datetime.datetime)
            Datetime object to pass to the scheduler
    """
    # TODO: I don't think this way of calculating the obs time is correct
    try:
        start_time = parser.parse(time)
        time_diff = datetime.timedelta(seconds = del_t)
        obs_time = start_time + time_diff

    except:
        logger.warning('Schedule block time could not be succesfully parsed')
        # TODO: placeholder epoch time in except block. Change!
        obs_time = datetime.datetime.now()

    return obs_time
