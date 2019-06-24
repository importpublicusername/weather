#system libraries
import pickle

#third party
from logzero import logger
#from loguru import logger

def writepickle(data, filename):
    with open(filename, 'wb') as f:
        # Pickle the 'data' dictionary using the highest protocol available.
        pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

def readpickle(filename):
    try:
        with open(filename, 'rb') as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it.
            data = pickle.load(f)
        return data
    except:
        logger.debug(f'file {filename} does not exist')
        return None