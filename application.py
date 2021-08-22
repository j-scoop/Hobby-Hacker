from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, Response, Markup, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
from operator import itemgetter


from functions import apology, login_required, create_figure, hrs_logged, suffix, custom_strftime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///hobby.db")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show summary of hobbies"""

    todayStr = custom_strftime('%a, {S} %B', datetime.now())

    # List of hobbies to pass to index.html
    hobbies = []
    hobbyList = db.execute("SELECT hobby FROM hobbies WHERE id = :id AND archived = 'false'", id = session["user_id"])
    for item in hobbyList:
        if item['hobby'] not in hobbies:
            hobbies.append(item['hobby'])

    # Pass in variables as args to render_template
    return render_template("index.html", hobbies = hobbies, today = todayStr)


@app.route("/archive", methods=["GET", "POST"])
@login_required
def archive():
    """Show summary of archived hobbies"""

    # List of hobbies to pass to archive.html
    hobbies = []
    hobbyList = db.execute("SELECT hobby FROM hobbies WHERE id = :id AND archived = 'true'", id = session["user_id"])
    for item in hobbyList:
        if item['hobby'] not in hobbies:
            hobbies.append(item['hobby'])

    todayStr = custom_strftime('%a, {S} %B', datetime.now())

    # Pass in variables as args to render_template
    return render_template("archive.html", hobbies = hobbies, today = todayStr)



@app.route("/hobby", methods=["GET", "POST"])
@login_required
def hobby_page(hobby = None):
    """Display custom page for individual hobby, show progress graph + table of entries.
    Allow user to delete entries"""

    # Access hobby submitted by index form
    if request.method == "POST":
        hobby = request.form.get("hobby")

        session['hobby'] = hobby

        # Add user inputted logs to database
        if request.form.get("time") != None and request.form.get("date") != None:
            time = request.form.get("time")
            # change date to python datetime format
            date = request.form.get("date")
            comment = request.form.get("comment")


            # Check total time logged for specified date is 24 hours or less
            totalTime = db.execute("""SELECT SUM(time) FROM hobby_logs WHERE id = :id AND hobby = :hobby AND date = :date""",
                    id = session["user_id"], hobby = hobby, date = date)

            totalLogged = totalTime[0]['SUM(time)']
            if totalLogged == None:
                totalLogged = 0
            if (totalLogged + int(time)) > 24:
                return apology("The total time you have entered is greater than 1 day.", 403)

            # Add to db
            db.execute("""INSERT INTO hobby_logs (id, hobby, time, date, comment) VALUES (:id, :hobby, :time, :date, :comment)""",
                    id = session["user_id"], hobby = hobby, time = time, date = date, comment = comment)
            # Redirect (refresh) to update table
            return redirect("/hobby")

        # Get hobby data for graph from database
        dbResults = db.execute("SELECT date, time FROM hobby_logs WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)

        # Take custom plot range from form and pass to create_figure()
        plot_range = request.form.get("plot_range")
        if request.form.get("archive") == "true":
            plot_range = '365'

        model_plot = ''
        plot_url = create_figure(hobby, dbResults, plot_range)
        model_plot = Markup('<img src="data:image/png;base64,{}" width: 360px; height: 288px>'.format(plot_url))

        # Display stats for hours logged
        # Get sum  of time logged for hobby from db
        totalResult = db.execute("""SELECT SUM(time) FROM hobby_logs WHERE id=:id and hobby=:hobby""",
                    id = session["user_id"], hobby = hobby)
        totalHrs = totalResult[0]['SUM(time)']
        if totalHrs == None:
            totalHrs = 0

        # Show total hrs all time, total per 'plot range' and average hrs per day for 'plot range'

        # Get all dates and time logged from db
        allResults = db.execute("""SELECT time, date FROM hobby_logs WHERE id = :id and hobby = :hobby""",
                id = session["user_id"], hobby = hobby)

        rangedStr = hrs_logged(allResults, plot_range)

        # Select values from hobby_logs table to populate entries table on webpage
        log_table = db.execute("""SELECT date, time, comment, key FROM hobby_logs WHERE id = :id AND hobby = :hobby""",
                    id = session["user_id"], hobby = hobby)

        # Sort log_table into date order
        # Sort results
        log_table.sort(key = itemgetter('date'))

        # Retreive key for row to delete from db
        key = request.form.get('delete')
        if key:
            # Delete from db table
            db.execute("""DELETE FROM hobby_logs WHERE id = :id AND key = :key""",
                        id = session["user_id"], key = key)
            return redirect("/hobby")

        # If amend form posted:
        if request.form.get("amend") != None:

            newName = request.form.get("name")
            newTime = request.form.get("reminder")
            newRepeat = request.form.getlist("repeat")

            # If changing repeat days, first delete all entries to rebuild later
            if newRepeat != []:

                # if user posted new time with form, update time variable
                if newTime != "":
                    time = newTime
                else:
                    # Fetch reminder time from db
                    time = db.execute("SELECT time FROM hobbies WHERE id = :id AND hobby = :hobby",
                            id = session["user_id"], hobby = hobby)

                db.execute("DELETE FROM hobbies WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)

                hobby = newName
                for day in newRepeat:
                    db.execute("INSERT INTO hobbies (id, hobby, day, time) VALUES (:id, :hobby, :day, :time)",
                                      id = session["user_id"], hobby = hobby, day = day, time = newTime)

            else:
                # Update hobbies and hobby_logs tables
                if newName != hobby:
                    db.execute("UPDATE hobbies SET hobby = :newName WHERE id = :id AND hobby = :hobby",
                        id = session["user_id"], hobby = hobby, newName = newName)

                    db.execute("UPDATE hobby_logs SET hobby = :newName WHERE id = :id AND hobby = :hobby",
                        id = session["user_id"], hobby = hobby, newName = newName)


                    # Update hobby variables
                    hobby = newName
                    session["hobby"] = newName

                if newTime != "":
                    db.execute("UPDATE hobbies SET time = :newTime WHERE id = :id AND hobby = :hobby",
                            id = session["user_id"], hobby = hobby, newTime = newTime)

            return redirect("/hobby")

        # Archive/ Delete functionality
        if request.form.get("archive") == "true":
            db.execute("UPDATE hobbies SET archived = 'true' WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)
            return render_template("archived.html", hobby = hobby, model_plot = model_plot, log_table = log_table, totalHrs = totalHrs)

        # Activate functionality
        if request.form.get("activate") == "true":
            db.execute("UPDATE hobbies SET archived = 'false' WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)
            return render_template("hobby.html", hobby = hobby, model_plot = model_plot, log_table = log_table, totalHrs = totalHrs, rangedStr = rangedStr)

        # Delete functionality
        if request.form.get("dlt") == "true":
            print("Deleting")
            db.execute("DELETE FROM hobbies WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)

            db.execute("DELETE FROM hobby_logs WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)

            return redirect("/")

    else:
        if session['hobby'] == None:
            return redirect("/")
        hobby = session['hobby']

        # Display custom plot for hobby
        # Get hobby data for graph from database
        dbResults = db.execute("SELECT date, time FROM hobby_logs WHERE id = :id AND hobby = :hobby",
                    id = session["user_id"], hobby = hobby)
        model_plot = ''
        plot_url = create_figure(hobby, dbResults)
        model_plot = Markup('<img src="data:image/png;base64,{}" width: 360px; height: 288px>'.format(plot_url))


        # Select values from hobby_logs table to populate entries table on webpage
        log_table = db.execute("""SELECT date, time, comment, key FROM hobby_logs WHERE id = :id AND hobby = :hobby""",
                    id = session["user_id"], hobby = hobby)

        # Display stats for hours logged
        # Get sum  of time logged for hobby from db
        totalResult = db.execute("""SELECT SUM(time) FROM hobby_logs WHERE id=:id and hobby=:hobby""",
                    id = session["user_id"], hobby = hobby)
        totalHrs = totalResult[0]['SUM(time)']

        # Show total hrs all time, total per 'plot range' and average hrs per day for 'plot range'

        # Get all dates and time logged from db
        allResults = db.execute("""SELECT time, date FROM hobby_logs WHERE id = :id and hobby = :hobby""",
                id = session["user_id"], hobby = hobby)

        rangedStr = hrs_logged(allResults)

    return render_template("hobby.html", hobby = hobby, model_plot = model_plot, log_table = log_table, totalHrs = totalHrs, rangedStr = rangedStr)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Setup variable for individual hobby pages
        session["hobby"] = None

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password confirmed
        elif not request.form.get("confirmation"):
            return apology("Please confirm password!", 403)

        # Check passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords did not match!", 403)

        # Insert username and password hash into db
        pwHash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :pwHash)",
                          username=request.form.get("username"), pwHash = pwHash)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

    return apology("Registration Unsuccesful", 403)


@app.route("/new", methods=["GET", "POST"])
@login_required
def log_new_hobby():
    """Add new hobby to db"""
    if request.method == "POST":
        hobby = request.form.get("hobby")
        if hobby == "":
            return apology("Hobby name required", 403)

        # Check if hobby already in db
        hobbyList = db.execute("SELECT hobby FROM hobbies WHERE id = :id", id = session["user_id"])

        for item in hobbyList:
            if hobby == item['hobby']:
                return apology("Hobby already logged", 403)

        repeat = request.form.getlist("repeat")

        time = request.form.get("reminder")
        format = "%H:%M"
        if time:
            timeObj = datetime.strptime(time, format)
        else:
            timeObj = None

        # If reminder time is given, ensure day is given
        if time and not repeat:
            return apology("If logging a reminder time you must select at least one day", 403)

        else:
            if repeat:
                for day in repeat:
                    db.execute("INSERT INTO hobbies (id, hobby, day, time) VALUES (:id, :hobby, :day, :time)",
                                      id = session["user_id"], hobby = hobby, day = day, time = timeObj)
            else:
                db.execute("INSERT INTO hobbies (id, hobby) VALUES (:id, :hobby)",
                                    id = session["user_id"], hobby = hobby)

    else:
        return render_template("new.html")

    return redirect("/")


@app.route("/manage", methods=["GET", "POST"])
@login_required
def manage():
    # List of hobbies to pass to index.html
    hobbies = []
    hobbyList = db.execute("SELECT hobby FROM hobbies WHERE id = :id", id = session["user_id"])
    for item in hobbyList:
        if item['hobby'] not in hobbies:
            hobbies.append(item['hobby'])

    # Pass in variables as args to render_template
    return render_template("manage.html", hobbies = hobbies)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
