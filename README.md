dublin-bus-telegram-bot
=====

Telegram Bot which responds to requests for real-time Dublin Bus data. This project is an extension for the python-telegram-bot open-source project. 
## Source
Clone the [python-telegram-bot](https://github.com/leandrotoledo/python-telegram-bot) repo and place the dublinbus.py file in the /examples/ directory.

## Dependencies
This extension requires multiple dependencies to work. [Suds](https://pypi.python.org/pypi/suds-jurko) is used to access the Dublin Bus SOAP-powered [API](http://rtpi.dublinbus.biznetservers.com/DublinBusRTPIService.asmx), and [Arrow](http://crsmithdev.com/arrow/) is used for timestamp parsing.

    $ pip install python-telegram-bot
    $ pip install suds-jurko
    $ pip install arrow

## Running
    $ python dublinbus.py
    
## Usage
  - **Stop Number** - Responds with real time departure information for current stop
    >**User:** *3190*
 
    >**Bot:** :busstop: Stop ID 49
    >8 Mountjoy Sq via Ballsbridge - in 3 mins
    >7 Mountjoy Sq via Ballsbridge - in 5 mins
    >66 Maynooth via Palmerstown - in 10 mins
    >25A Lucan S.C. via Palmerstown - in 13 mins
    >4 Harristown via City Centre - in 13 mins
  - **Location** - Responds with stop numbers nearby to location
    >**User:** [current location]
    
    >**Bot:** :round_pushpin: Closest Stops:
    >399: Pearse Street, Westland Row
    >495: Westland Row, Pearse Station
    >7588: Pearse Street, Tara Street
