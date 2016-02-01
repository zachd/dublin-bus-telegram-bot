#!/usr/bin/env python

"""
This Bot uses the Updater class to handle the bot.
First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and the CLI-Loop is entered.
Usage:
Basic Echobot example, repeats messages.
Type 'stop' on the command line to stop the bot.
"""

from telegram import Updater
import sys
import arrow
import logging
import telegram
import urllib, json
from suds.xsd.doctor import ImportDoctor, Import
from suds.client import Client

# Enable logging
root = logging.getLogger()
root.setLevel(logging.WARNING)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = \
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

logger = logging.getLogger(__name__)
DEF_INCREMENT = float(0.001)
CLIENT = None

def main():
    global CLIENT
    # Create the EventHandler and pass it your bot's token.
    updater = Updater("TOKEN_HERE")
    
    # Set URL to Dublin Bus RTPI
    url = 'http://rtpi.dublinbus.ie/DublinBusRTPIService.asmx?wsdl'

    # Import the correct XML Schema and namespace
    imp = Import('http://www.w3.org/2001/XMLSchema', location='http://www.w3.org/2001/XMLSchema.xsd')
    imp.filter.add('http://dublinbus.ie/')
    d = ImportDoctor(imp)

    # Setup the global client with the import doctor and url
    try:
        CLIENT = Client(url, doctor=d) 
        print "Suds Client Connected"
    except:
        print "Client connection error"

    # UTF-8: http://stackoverflow.com/a/17628350
    reload(sys)  # Reload does the trick!
    sys.setdefaultencoding('UTF8')

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.addTelegramCommandHandler("start", start)
    dp.addTelegramCommandHandler("help", help)

    # on noncommand i.e message - echo the message on Telegram
    dp.addTelegramMessageHandler(message)

    # on error - print error to stdout
    dp.addErrorHandler(error)

    # Start the Bot
    updater.start_polling(timeout=5)

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()

# Command Handlers
def start(bot, update):
    bot.sendMessage(update.message.chat_id, text='Hi!')


def help(bot, update):
    bot.sendMessage(update.message.chat_id, text='Help!')


def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))

# Message Handler
def message(bot, update):
    global CLIENT
    chat_id = update.message.chat_id
    increment = DEF_INCREMENT
    message = update.message
    text = ''

    # Check if we get a message
    if (message):
        if(message.text):
            text = message.text.encode('utf-8')
            msg = ": " + text
        elif(message.location):
            lat = message.location.latitude
            lng = message.location.longitude
            msg = " sent Location (" + str(lat) +"," + str(lng) + ")"
        else:
            msg = ": <Unknown Message>"

        # Log the message to the console
        print('[' + str(message.date) + '] ' + message.from_user.username + msg)
        
        # If the message a location
        if(message.location):

            # Send the typing action
            bot.sendChatAction(chat_id=chat_id, action=telegram.ChatAction.TYPING)

            # Request the stops for near the current location
            url = "http://dublinbus.ie/Templates/Public/RoutePlannerService/RTPIMapHandler.ashx"

            # Keep increasing local search
            for i in range(5):
                params = "?ne=" + str(lat + increment) + "," + str(lng + increment) + "&sw=" + str(lat - increment) + "," + str(lng - increment)
               
                # Attempt to request stop data and read JSON response
                try:
                    response = urllib.urlopen(url + params)
                    data = json.loads(response.read())
                except:
                    response, data = None
                    print "URL or JSON Error!"
                if len(data['points']) > 0:
                    break
                increment *= float(2)

            # Get haversine distance to each stop lat,lng and sort ascending
            for stop in data['points']:
                stop['dist'] = haversine(lat, lng, stop['lat'], stop['lng'])
            closest = sorted(data['points'], key=lambda k: k['dist']) 
            
            # Iterate through first 5 stops and build string response
            stringtoreturn = ''
            length = 5 if (len(closest) >= 5) else len(closest)
            for i in range(length):
                stringtoreturn += closest[i]['stopnumber'] + ": " + closest[i]['address'] + "\n"

            # Send closest stops response back to chat_id
            bot.sendMessage(chat_id=chat_id,
                            text=telegram.Emoji.ROUND_PUSHPIN + 'Closest Stops:\n' + stringtoreturn)

        # If the message a digit
        if(text.isdigit()):

            # Send the typing action
            bot.sendChatAction(chat_id=chat_id, action=telegram.ChatAction.TYPING)

            # Request the real time stop data for the stop id
            try:
                soapresult = CLIENT.service.GetRealTimeStopData(text, 1)
            except:
                soapresult = None
                print "Suds Error!"

            # Check if the stop ID was found
            if(soapresult and hasattr(soapresult.diffgram[0], 'DocumentElement')):
                results = soapresult.diffgram[0].DocumentElement[0].StopData
                stringtoreturn = ''

                # Iterate over results
                for bus in results:
                    timestamp = arrow.get(bus.StopMonitoringDelivery_ResponseTimestamp[0])
                    scheduled = arrow.get(bus.MonitoredCall_AimedArrivalTime[0])
                    arrival = arrow.get(bus.MonitoredCall_ExpectedArrivalTime[0])
                    difference = (arrival - timestamp).total_seconds()
                    stringtoreturn += bus.MonitoredVehicleJourney_PublishedLineName[0] + ' ' + bus.MonitoredVehicleJourney_DestinationName[0]
                    stringtoreturn += ' - ' + ('in *' + prettify(difference) + '*' if difference > 30 else "*due(")#scheduled.format('HH:mm')
                    #stringtoreturn += (' (+' + (prettify(difference) if difference > 60 else '1 min') + ')' if difference > 0 else '')
                    #stringtoreturn += (telegram.Emoji.VERTICAL_TRAFFIC_LIGHT if bus.MonitoredVehicleJourney_InCongestion[0] != "false" else '')
                    stringtoreturn += (telegram.Emoji.BUS if bus.MonitoredCall_VehicleAtStop[0] != "false" else '')
                    stringtoreturn += '\n'

                # Reply the message
                bot.sendMessage(chat_id=chat_id,
                                text=telegram.Emoji.BUS_STOP + 'Stop ID *' + text + '*:\n' + stringtoreturn,
                                parse_mode=telegram.ParseMode.MARKDOWN)

            # Else if soapresult has schema data then no buses found
            elif(hasattr(soapresult, 'schema') and len(soapresult.schema[0].element[0].complexType[0].choice[0].element[0].complexType[0])):
                bot.sendMessage(chat_id=chat_id,
                                text='No buses available for Stop ' + text)

            # Otherwise the stop ID must be invalid
            else:
                bot.sendMessage(chat_id=chat_id,
                                text='Stop ID not found')

# Prettify: http://stackoverflow.com/a/18421524
def prettify(time_diff_secs):
    # Each tuple in the sequence gives the name of a unit, and the number of
    # previous units which go into it.
    weeks_per_month = 365.242 / 12 / 7
    intervals = [('min', 60), ('hr', 60), ('day', 24), ('wk', 7),
                 ('mnth', weeks_per_month), ('yr', 12)]
    unit, number = 'sec', abs(time_diff_secs)
    for new_unit, ratio in intervals:
        new_number = float(number) / ratio
        # If the new number is too small, don't go to the next unit.
        if new_number < 1:
            break
        unit, number = new_unit, new_number
    shown_num = int(number)
    return '{} {}'.format(shown_num, unit + ('' if shown_num == 1 else 's'))

# Haversine: http://stackoverflow.com/a/4913653
from math import radians, cos, sin, asin, sqrt
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r

if __name__ == '__main__':
    main()
