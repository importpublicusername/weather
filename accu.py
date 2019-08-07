# system libraries
import configparser
from statistics import mean
import datetime
import logging

# local file
from dill import writepickle
from dill import readpickle

logger = logging.getLogger()
logger.setLevel(20)

filename = r'config.txt'
config = configparser.ConfigParser()
config.read(filename)
accuweatherconfig = config._sections['accuweather']
urlfuture_base = 'https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/'
postalcode = accuweatherconfig['postalcode']
apikey = accuweatherconfig['apikey']
locations_url = f'https://dataservice.accuweather.com/locations/v1/postalcodes/search?apikey={apikey}&q={postalcode}'
mode = accuweatherconfig['mode']

#TODO - this is deprecated and needs to be replaced...what is equiv that can be used local and lambda
import botocore.vendored.requests as requests

slack_webhook = config._sections['slack']['webhook']

state_file = 'state.pickle'
state_location = 'location.pickle'


def checkrain(max_of_probs, max_of_liquids):
    if max_of_probs > 52 and max_of_probs < 75:
        msg = f'OK chance of rain; max prob {max_of_probs}%, max {max_of_liquids} inches'
        logger.info(msg)
        result = (msg, 1)
    elif max_of_probs >= 75:
        msg = f'Really good change for precip- {max_of_probs}%, max {max_of_liquids} inches'
        logger.info(msg)
        result = (msg, 2)
    elif max_of_probs == 0:
        msg = f'It is bone dry out there for the next 12 hours at least'
        logger.info(msg)
        result = (msg, 3)
    elif max_of_probs > 0 and max_of_probs <= 52:
        msg = f'Not likely for rain in next 12 hours, {max_of_probs}%, max {max_of_liquids} inches'
        logger.info(msg)
        result = (msg, 4)
    else:
        msg = f'not sure what is going on, {max_of_probs}%, max {max_of_liquids} inches'
        logger.error(msg)
        result = (msg, -1)
    return result


def checkwind(maxwind):
    # result of type tuple like ('string of text', case1-x)
    if maxwind > 10 and maxwind < 20:
        msg = f'It is a bit windy with max of {maxwind} mph'
        logger.info(msg)
        result = (msg, 1)
    elif maxwind <= 10 and maxwind > 5:
        msg = f'Pretty calm with max of {maxwind} mph'
        logger.info(msg)
        result = (msg, 2)
    elif maxwind <= 5:
        msg = f'Holy smokes it is calm out there with max of {maxwind} mph'
        logger.info(msg)
        result = (msg, 3)
    elif maxwind >= 20:
        msg = f'Batten down the hatches mate with max of {maxwind} mph'
        logger.info(msg)
        result = (msg, 4)
    else:
        msg = f'I have no idea about the wind with max of {maxwind} mph'
        logger.errror(msg)
        result = (msg, -1)
    return result


def getlocation():
    locationstate = readpickle(state_location, mode)
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
        writepickle(loc_state, state_location, mode)
        return locationcode


def main():

    locationcode = getlocation()
    urlfuture = urlfuture_base + locationcode
    r = requests.get(urlfuture+f'?apikey={apikey}&details=true')
    results12hr = r.json()
    state = readpickle(state_file, mode)

    listofprobs = []  # PrecipitationProbability
    liquids = []  # TotalLiquid
    wind_speeds = []  # wind speed list
    forecast = []
    for future in results12hr:
        precip_prob = future['PrecipitationProbability']
        listofprobs.append(precip_prob)
        
        liquid_amt = future['TotalLiquid']['Value']
        liquids.append(liquid_amt)
        
        wind_amt = future['Wind']['Speed']['Value']
        wind_speeds.append(wind_amt)
        logger.debug(str(wind_amt))
        
        d = datetime.datetime.strptime(future['DateTime'][0:-6], '%Y-%m-%dT%H:%M:%S') #%z not work on py 3.6
        hour = d.hour
        if hour > 12:
            hour = hour - 12
            hour = f'{hour}pm'
        elif hour == 0:
            hour = '12am'
        else:
            hour = f'{hour}am'
        line = f'{d.month}-{d.day} {hour}: {precip_prob}%, {liquid_amt} inches, {wind_amt} mph'
        forecast.append(line)
        logger.debug(line)
    # print(forecast)
    max_of_probs = max(listofprobs)
    max_of_liquids = max(liquids)
    logger.debug(f'max of probs {max_of_probs} max of inches {max_of_liquids}')

    avg_of_probs = mean(listofprobs)
    avg_of_liquids = mean(liquids)
    logger.debug(f'avg of probs {avg_of_probs} avg of inches {avg_of_liquids}')

    max_of_wind = max(wind_speeds)
    
    wind_msgs = checkwind(max_of_wind)
    rain_msgs = checkrain(max_of_probs, max_of_liquids)

    msgs = []
    if state:
        state_rain, state_wind, lastcheck = state

        if state_rain != rain_msgs[1]:
            logger.debug('rain changed enough to report')
            msgs.append(rain_msgs[0])
        if state_wind != wind_msgs[1]:
            logger.debug('wind changed enough to report')
            msgs.append(wind_msgs[0])
        
        if msgs == [] and datetime.datetime.now() - datetime.timedelta(minutes=95) > lastcheck:
            if max_of_probs > 0:
                logger.debug('It has been a while since last report - give an update')
                msgs.append(rain_msgs[0])
            if max_of_wind >= 20:
                logger.debug('It has been a while since last report WIND - give an update')
                msgs.append(wind_msgs[0])
    else:
        logger.debug('no current state or previous chance of rain')
        msgs = [rain_msgs[0], wind_msgs[0]]

    logger.debug(f'msgs {msgs}')

    if len(msgs) > 0:
        logger.info(f'sending msgs {msgs}')
        
        mystring = ' '
        for msg in msgs:
            mystring += msg + '\n'
        requests.post(slack_webhook, json={"text": mode + mystring})
        logger.debug(mystring)

        mystring = ''
        for line in forecast:
            mystring += line + '\n'
        requests.post(slack_webhook, json={"text": mystring})
        logger.debug(mystring)
    else:
        m = f'Nothing to report {max_of_probs}% for {max_of_liquids} inches, {max_of_wind} mph'
        logger.info(m)
        if logger.level == 10:  # then debug enabled
            requests.post(slack_webhook, json={"text": m})

            mystring = 'DEBUG === '
            for line in forecast:
                mystring += line + '\n'
            requests.post(slack_webhook, json={"text": mystring})
            logger.debug(mystring)
    
    # save the state for next go around
    writepickle([rain_msgs[1], wind_msgs[1], datetime.datetime.now()], state_file, mode)  # save state of the last alert


if __name__ == "__main__":
    main()
