#!/usr/bin/env python
#
# Simple Bot to reply Telegram messages
# Copyright (C) 2015 Leandro Toledo de Souza <leandrotoeldodesouza@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].

import sys
import arrow
import logging
import telegram
import urllib, json
from suds.xsd.doctor import ImportDoctor, Import
from suds.client import Client

LAST_UPDATE_ID = None

def main():
    global LAST_UPDATE_ID, DEF_INCREMENT

    # Telegram Bot Authorization Token and settings
    bot = telegram.Bot('YOUR_TELEGRAM_BOT_API_KEY')
    DEF_INCREMENT = float(0.001)
    
    # Set URL to Dublin Bus RTPI
    url = 'http://rtpi.dublinbus.biznetservers.com/DublinBusRTPIService.asmx?wsdl'

    # Import the correct XML Schema and namespace
    imp = Import('http://www.w3.org/2001/XMLSchema', location='http://www.w3.org/2001/XMLSchema.xsd')
    imp.filter.add('http://dublinbus.ie/')
    d = ImportDoctor(imp)

    # Setup the client with the import doctor and url
    client = Client(url, doctor=d) 

    # UTF-8: http://stackoverflow.com/a/17628350
    reload(sys)  # Reload does the trick!
    sys.setdefaultencoding('UTF8')

    # This will be our global variable to keep the latest update_id when requesting
    # for updates. It starts with the latest update_id if available.
    try:
        LAST_UPDATE_ID = bot.getUpdates()[-1].update_id
    except IndexError:
        LAST_UPDATE_ID = None

    # Get updates indefinitely
    while True:
        echo(bot, client)


def echo(bot, client):
    global LAST_UPDATE_ID, DEF_INCREMENT

    # Request updates after the last updated_id
    try:
        updates = bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10)
    except telegram.error.TelegramError:
        updates = []

    # Iterate through available updates
    for update in updates:
        chat_id = update.message.chat_id
        increment = DEF_INCREMENT
        message = update.message
        text = ''

        # Check if we get a message
        if (message):
            if(message.text):
                text = message.text.encode('utf-8')
                msg = ": " + text
            if(message.location):
                lat = message.location.latitude
                lng = message.location.longitude
                msg = " sent Location (" + str(lat) +"," + str(lng) + ")"

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
                    print url + params

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
                    soapresult = client.service.GetRealTimeStopData(text, 1)
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
                        stringtoreturn += ' - ' + ('in ' + prettify(difference) if difference > 30 else "due")
                        stringtoreturn += (telegram.Emoji.BUS if bus.MonitoredCall_VehicleAtStop[0] != "false" else '')
                        stringtoreturn += '\n'

                    # Reply with the message
                    bot.sendMessage(chat_id=chat_id,
                                    text=telegram.Emoji.BUS_STOP + 'Stop ID ' + text + ':\n' + stringtoreturn)

                # Else if soapresult has schema data then no buses found
                elif(hasattr(soapresult, 'schema') and len(soapresult.schema[0].element[0].complexType[0].choice[0].element[0].complexType[0])):
                    bot.sendMessage(chat_id=chat_id,
                                    text='No buses available for Stop ' + text)

                # Otherwise the stop ID must be invalid
                else:
                    bot.sendMessage(chat_id=chat_id,
                                    text='Stop ID not found')
                
        # Updates global offset to get the new updates
        try:
            LAST_UPDATE_ID = update.update_id + 1
        except telegram.error.TelegramError as e:
            print "Telegram Error({0}): {1}".format(e.errno, e.strerror)

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

# Main function
if __name__ == '__main__':
    main()