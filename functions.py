import os
import requests
import urllib.parse
import matplotlib.pyplot as plt
from operator import itemgetter
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import base64
import io
from datetime import datetime, date
import numpy as np
from matplotlib.dates import WeekdayLocator, DayLocator
from matplotlib.dates import MO, TU, WE, TH, FR, SA, SU
import matplotlib.dates as mdates
import matplotlib.ticker as plticker
from dateutil.relativedelta import relativedelta
import math

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# Get todays date and format as string
def suffix(d):
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def custom_strftime(format, t):
    return t.strftime(format).replace('{S}', str(t.day) + suffix(t.day))


def hrs_logged(allResults, time_range = None):
    """Get time logged as a string per time_range"""
    today_obj = datetime.today()
    rangedTotal = 0

    if time_range == "7" or time_range == None:
        # Get date 1 week ago from today

        # date_diff = timedelta(weeks = 1)
        # date_limit = today_obj - date_diff
        date_limit = today_obj - relativedelta(weeks=1)
        endStr = "week"

    elif time_range == "30":
        # Get date 1 month ago from today
        date_limit = datetime.now() - relativedelta(months=1)
        endStr = "month"

    else:
        # Get sum of hours logged from past year
        date_limit = datetime.now() - relativedelta(years=1)
        endStr = "year"

    # Convert db date strings to datetime and check if within range
    for result in allResults:
        if (datetime.strptime(result['date'], "%Y-%m-%d")) < date_limit:
            result['time'] = 0
        rangedTotal += result['time']

    # format ranged total as string to pass to webpage
    rangedStr = str(rangedTotal) + " hours logged this " + endStr

    return rangedStr


def create_figure(hobby, dbResults, x_range = None):
    # Move to functions.py
    """Create custom figure for specific hobby"""

    # If no x-axis range given, set to 7
    if not x_range:
        x_range = 7

    # Clear plot if already being displayed
    plt.close()

    dates = []
    times = []

    # Sort results
    dbResults.sort(key = itemgetter('date'))

    # TODO: Allow user to select time period for graph (past 7 days, 30 days)

    # Amend for multiple entries on same date
    i = 1
    for result in dbResults:
        if i < len(dbResults):
            # If matching dates, add times together
            if result['date'] == dbResults[i]['date']:
                result['time'] = result['time'] + dbResults[i]['time']
                dbResults[i]['time'] = 0
            # Delete duplicate date
            if dbResults[i]['time'] == 0:
                del dbResults[i]
        i += 1

    # Convert data into x, y lists
    for result in dbResults:
        dates.append(result['date'])
        times.append(result['time'])

    # numpy test scale x acis
    dates = np.array(dates)
    times = np.array(times)

    # Convert from db string to datetime
    dateFormat = "%Y-%m-%d"
    xdates = [datetime.strptime(date, dateFormat) for date in dates]
    # convert to matplotlib dates
    xdates = mdates.date2num(xdates)


    # Create plot
    ## Commented out for numpy test
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ##

    # ax.plot(xdates, times, "#3fc447")
    ax.set_axisbelow(True)
    plt.xlabel("date")
    plt.ylabel("time spent (hrs)")

    # Background colour
    fig.set_facecolor('#edf5f4')
    ax.set_facecolor('#cedcf2')

    # Set axis ranges
    today_datetime = date.today()
    # Convert to matplotlib
    today_mpl = mdates.date2num(today_datetime)

    if x_range == '30':
        # Take 30 mpl days
        x_lim = today_mpl - date(1, 2, 1).toordinal()
        plt.title(hobby + " - Past month")
        plt.grid(b=None, which='both', axis='both')
        # Add major ticks every day
        locator = mdates.AutoDateLocator()
        locator.intervald['DAILY'] = 7
        ax.bar(xdates, times, width = 0.2)

        ax.set_xlim([x_lim, today_mpl])

        plt.setp(ax.get_xticklabels(), rotation=45)

        # format dates as matplotlib dates and add x axis ticks
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))

    elif x_range == '365':
        # Take 365 mpl days
        # x_lim = today_mpl - date(1, 12, 1).toordinal()

        # Get past date 1 year ago via datetime
        last_year = datetime.now() - relativedelta(months=12)
        x_lim = mdates.date2num(last_year)

        ax.set_xlim([x_lim, today_mpl])

        plt.title(hobby + " - Past year")
        plt.grid(b=None, which='both', axis='both')
        # Add major ticks every month
        ax.xaxis.set_major_locator(mdates.MonthLocator())

        # format date ticks
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        plt.setp(ax.get_xticklabels(), rotation='45')


        # Pad margins so that markers don't get clipped by the axes
        plt.margins(0.2)
        # Tweak spacing to prevent clipping of tick-labels
        plt.subplots_adjust(bottom=0.15)
        ax.bar(xdates, times, width = 1)


    # Default to past 7 days
    else:
        x_lim = today_mpl - date(1, 1, 6).toordinal()
        plt.title(hobby + " - Past week")
        plt.grid(b=None, which='both', axis='both')
        # Should add ticks at 'monday' on plot
        locator = mdates.AutoDateLocator()
        locator.intervald['DAILY'] = 7
        ax.bar(xdates, times, width = 0.1)

        plt.draw()
        ticks = ax.get_xticklabels()

        plt.setp(ax.get_xticklabels(), rotation=45)

        # format dates as matplotlib dates and add x axis ticks
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))

        ax.set_xlim([(x_lim - 0.5), (today_mpl + 0.5)])

    # Scale y axis
    def round_to(n, precision):
        """Round number to nearest 0.5"""
        correction = 0.5 if n >= 0 else -0.5
        return int( n/precision+correction ) * precision

    if len(times) >= 1:
        ax.set_ylim(bottom=0, top=round_to((max(times) + 0.25), 0.5))


    # Set y-axis ticker interval
    yloc = plticker.MultipleLocator(base=0.5) # this locator puts ticks at regular intervals
    ax.yaxis.set_major_locator(yloc)

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    return plot_url

