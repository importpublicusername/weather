#system libraries
import configparser
from statistics import mean
import datetime
import logging

#third party
import requests
import logzero
from logzero import logger

#local file
from dill import writepickle
from dill import readpickle

filename = r'config.txt'
config = configparser.ConfigParser()
config.read(filename)
accuweatherconfig = config._sections['accuweather']
urlfuture_base = 'https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/'
postalcode =  accuweatherconfig['postalcode']
apikey = accuweatherconfig['apikey']
locations_url = f'https://dataservice.accuweather.com/locations/v1/postalcodes/search?apikey={apikey}&q={postalcode}'

slack_webhook = config._sections['slack']['webhook']

state_file = 'state.pickle'
state_location = 'location.pickle'

def checkrain(max_of_probs, max_of_liquids):
    msgs = []
    if max_of_probs > 55 and max_of_probs < 75:
        msg = f'OK chance of rain; max prob {max_of_probs}%, max {max_of_liquids} inches'
        logger.info(msg)
        msgs.append(msg)
    elif max_of_probs >= 75:
        msg = f'really good change for precip- {max_of_probs}%, max {max_of_liquids} inches'
        logger.info(msg)
        msgs.append(msg)
    else:
        logger.debug(f'not likely for rain in next 12 hours {max_of_probs}')
        writepickle(None, state_file)
    return msgs

def getlocation():
    locationstate = readpickle(state_location)
    logger.debug(str(locationstate))
    if locationstate and postalcode == locationstate['postalcode']:
        logger.debug('saved value is same as configured value, no lookup needed')
        logger.debug(str([postalcode == locationstate['postalcode'], postalcode, locationstate['postalcode']]))
        return locationstate['locationcode']
    else:
        logger.debug('need to look it up')
        locationcode = requests.get(locations_url).json()[0]['Key']
        loc_state = {'postalcode': postalcode, 'locationcode': locationcode}
        logger.debug('new location {}', loc_state)
        writepickle(loc_state, state_location)
        return locationcode

def main():

    locationcode = getlocation()
    urlfuture = urlfuture_base + locationcode
    r = requests.get(urlfuture+f'?apikey={apikey}&details=true')
    results12hr = r.json()
    state = readpickle(state_file)

    listofprobs = [] #PrecipitationProbability
    liquids = [] #TotalLiquid
    forecast = []
    for future in results12hr:
        precip_prob = future['PrecipitationProbability']
        listofprobs.append(precip_prob)
        liquid_amt = future['TotalLiquid']['Value']
        liquids.append(liquid_amt)
        d = datetime.datetime.strptime(future['DateTime'][0:-6], '%Y-%m-%dT%H:%M:%S') #%z not work on py 3.6
        hour = d.hour
        if hour > 12:
            hour = hour - 12
            hour = f'{hour}pm'
        elif hour == 0:
            hour = '12am'
        else:
            hour = f'{hour}am'
        line = f'{d.month}-{d.day} {hour}: {precip_prob}% {liquid_amt} inches'
        forecast.append(line)
        logger.debug(line)

    max_of_probs = max(listofprobs)
    max_of_liquids = max(liquids)
    logger.debug(f'max of probs {max_of_probs} max of inches {max_of_liquids}')

    avg_of_probs = mean(listofprobs)
    avg_of_liquids = mean(liquids)
    logger.debug(f'avg of probs {avg_of_probs} avg of inches {avg_of_liquids}')

    if state:
        state_prob, state_liquid = state
        if abs(state_prob - max_of_probs) > 10 or abs(max_of_liquids - state_liquid) > .1:
            logger.debug('things changed enough to report')
            msgs = checkrain(max_of_probs, max_of_liquids)
        else:
            logger.debug("things didn't change that much from last report")
            msgs = []
    else:
        logger.debug('no current state or previous chance of rain')
        msgs = checkrain(max_of_probs, max_of_liquids)

    logger.debug(f'msgs {msgs}')

    if len(msgs) > 0:
        writepickle([max_of_probs, max_of_liquids], state_file) #save state of the last alert
        logger.info(f'sending msgs {msgs}')
        requests.post(slack_webhook, json={"text": str(msgs)})
        mystring = ''
        for line in forecast:
            mystring += line + '\n'
        requests.post(slack_webhook, json={"text": mystring})
        logger.debug(mystring)
    else:
        m = f'Not much going on for rain or no change {max_of_probs}% for {max_of_liquids} inches'
        logger.info(m)
        if logger.isEnabledFor(logging.DEBUG):
            requests.post(slack_webhook, json={"text": m})

            mystring = ''
            for line in forecast:
                mystring += line + '\n'
            requests.post(slack_webhook, json={"text": mystring})
            logger.debug(mystring)

if __name__ == "__main__":
    logzero.loglevel(logging.INFO)
    main()
