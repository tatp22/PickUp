from flask import Flask,request,render_template,redirect, url_for,session,flash
from functools import wraps
import MySQLdb
from MySQLdb import escape_string as thwart
from wtforms import Form, BooleanField, TextField, PasswordField, IntegerField, validators
from flask_socketio import SocketIO, emit
import gc
import os
import datetime
from threading import Thread, Event

# Import modules for CGI handling
import cgi, cgitb

conn = MySQLdb.connect('GucciGang5.mysql.pythonanywhere-services.com', 'GucciGang5', 'cs411cs411', \
       'GucciGang5$guccigang')

#DATABASE = '/home/GucciGang5/data.db'

app = Flask(__name__)
app.config.from_object(__name__)

app.secret_key = 'yjkimb'

#def connect_db():
#	return sqlite3.connect(app.config['DATABASE'])
@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

class RegistrationForm(Form):
    username = TextField('Username', [validators.Length(min=1,max=20)])
    real_name = TextField('First Name', [validators.Required()])
    age = IntegerField('Age',[validators.NumberRange(min=1,max=140)])
    password = PasswordField("Password (DON'T PUT YOUR REAL ONE, THIS IS UNHASHED)", [validators.Required(),
                                          validators.EqualTo('confirm', message="Passwords must match")])
    confirm = PasswordField('RepeatPassword')

    accept_tos = BooleanField('I accept the terms of service and the privacy notice (Last updated 12 Jan 2069)',
                                [validators.Required()])

@app.route('/', methods = ['post', 'get'])
def home():
    cursor = conn.cursor()
    cursor.execute("""SELECT DISTINCT people.Username, events.name, events.Sports, events.Location, events.Time, events.Creator
                    FROM    people, Plays, PlaysAt, events, Participants
                    WHERE (events.Name = Participants.EventName) AND (people.Username = Plays.Username AND Plays.SportName = events.Sports) AND
                    (PlaysAt.LocationName = events.Location AND people.Username = PlaysAt.Username) AND
                    (events.MaxAge >= people.Age AND events.MinAge <= people.Age) AND
                    (events.MaxSkill >= Plays.SkillLvl AND events.MinSkill <= Plays.SkillLvl) AND
                     (events.Creator <> '{0}')
                    """.format(session['username']))

    rows = cursor.fetchall()
    data = []
    for row in rows:
        if row[0] == session['username']:
            data.append(row)
    cursor.execute('select EventName from Participants where PersonUsername = "{0}"'.format(session['username']))

    rows2 = cursor.fetchall()
    data2 = [row[0] for row in rows2]
    noti_num = 1
    cursor.close()
    return render_template('home.html', noti_num = noti_num)

@app.route('/test-form', methods = ['post', 'get'])
def test_form():
    return render_template('test-form.html')

@app.route('/test-form_success', methods = ['post'])
def test_form_post():
    sports = request.form['sports']
    cursor = conn.cursor()
    cursor.execute('insert into sports values ("' + sports + '")')
    conn.commit()
    cursor.close()
    return render_template('test-form.html')

@app.route('/live_events', methods = ['post', 'get'])
def live_events():
    cursor = conn.cursor()

    #cursor.execute("""SELECT DISTINCT Name,Sports,NumPlayers,Location,Time,MinAge,
    #                         MaxAge,MinSkill,MaxSkill,Creator
    #                  FROM events,Participants
    #                  WHERE events.Name <> Participants.EventName
    #                """)

    cursor.execute("""SELECT events.*,C.cnt
                      FROM events
                      INNER JOIN (SELECT EventName, count(EventName) as cnt
                        FROM Participants
                        GROUP BY EventName) C ON events.Name = C.EventName;
                    """)
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute('select EventName from Participants where PersonUsername = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row[0] for row in rows2]

    # Query for getting number of participants:
    # select Count(PersonUsername) FROM Participants WHERE EventName={0}.format(nameOfEvent);

    # Constraints

    # Playable Sports?

    playsQuery = 'select SportName from Plays where Username = "' + session['username'] + '"'
    cursor.execute(playsQuery)
    playsQueryRows = cursor.fetchall()
    playsQueryData = [row[0] for row in playsQueryRows]

    # In Skill Level Range?

    levelRangeQuery = 'Select SportName, SkillLvl From Plays Where Username = "' + session['username'] + '"'
    cursor.execute(levelRangeQuery)
    levelRangeRows = cursor.fetchall()
    #levelRangeData = [ row for row in levelRangeRows ]
    levelRangeData = { row[0]: row[1] for row in levelRangeRows }
    cursor.close()
    return render_template('live_events.html', data = data, data2 = data2, playsData = playsQueryData, levelData = levelRangeData)

@app.route('/my_events', methods = ['post', 'get'])
def my_events():
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE EXISTS (SELECT PersonUsername FROM Participants WHERE PersonUsername = '{0}' AND Name = EventName) OR Creator = '{0}'".format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                    SELECT PersonUsername, EventName, Sports, num, SkillLvl
                    FROM (
                    SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                    FROM(
                    SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                    FROM Participants part, Plays play, events event
                    WHERE event.sports = play.SportName AND
                    event.Name = part.EventName AND
                    part.PersonUsername = play.Username
                    ORDER BY EventName, SkillLvl
                    ) a
                    ) t
                    WHERE mod(num, 2) = 0
                        """)
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    flash(data2)
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                        SELECT PersonUsername, EventName, Sports, num, SkillLvl
                        FROM (
                        SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                        FROM(
                        SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                        FROM Participants part, Plays play, events event
                        WHERE event.sports = play.SportName AND
                        event.Name = part.EventName AND
                        part.PersonUsername = play.Username
                        ORDER BY EventName, SkillLvl
                        ) a
                        ) t
                        WHERE mod(num, 2) = 1
                        """)
    rows3 = cursor.fetchall()
    data3 = [row for row in rows3]
    cursor.execute("SELECT * FROM Participants")
    rows4 = cursor.fetchall()
    data4 = [row for row in rows4]


    cursor.close()
    return render_template('my_events.html', data = data, data_team1 = data2, data_team2 = data3, data_participates= data4)

@app.route('/testadv', methods = ['post', 'get'])
def testadv():
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE EXISTS (SELECT PersonUsername FROM Participants WHERE PersonUsername = '{0}' AND Name = EventName) OR Creator = '{0}'".format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                    SELECT PersonUsername, EventName, Sports, num, SkillLvl
                    FROM (
                    SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                    FROM(
                    SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                    FROM Participants part, Plays play, events event
                    WHERE event.sports = play.SportName AND
                    event.Name = part.EventName AND
                    part.PersonUsername = play.Username
                    ORDER BY EventName, SkillLvl
                    ) a
                    ) t
                    WHERE mod(num, 2) = 0
                        """)
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    flash(data2)
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                        SELECT PersonUsername, EventName, Sports, num, SkillLvl
                        FROM (
                        SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                        FROM(
                        SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                        FROM Participants part, Plays play, events event
                        WHERE event.sports = play.SportName AND
                        event.Name = part.EventName AND
                        part.PersonUsername = play.Username
                        ORDER BY EventName, SkillLvl
                        ) a
                        ) t
                        WHERE mod(num, 2) = 1
                        """)
    rows3 = cursor.fetchall()
    data3 = [row for row in rows3]
    cursor.execute("SELECT * FROM Participants")
    rows4 = cursor.fetchall()
    data4 = [row for row in rows4]


    cursor.close()
    return render_template('testadv.html', data = data, data_team1 = data2, data_team2 = data3, data_participates= data4)

@app.route('/notif_join', methods = ['POST'])
def notif_join():
    #pName = request.form['updateevent'][0]
    creator = session['username']
    eName = request.form['item0'] #event name
    eLoc = request.form['item2'] #event location
    cName = request.form['item3'] #creator name
    cursor = conn.cursor()
    query = "INSERT INTO Participants VALUES ('{0}','{1}','{2}','{3}')".format(creator,eName,eLoc,cName)
    cursor.execute(query)
    conn.commit()

    cursor.execute("SELECT * FROM events WHERE EXISTS (SELECT PersonUsername FROM Participants WHERE PersonUsername = '{0}' AND Name = EventName) OR Creator = '{0}'".format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                    SELECT PersonUsername, EventName, Sports, num, SkillLvl
                    FROM (
                    SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                    FROM(
                    SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                    FROM Participants part, Plays play, events event
                    WHERE event.sports = play.SportName AND
                    event.Name = part.EventName AND
                    part.PersonUsername = play.Username
                    ORDER BY EventName, SkillLvl
                    ) a
                    ) t
                    WHERE mod(num, 2) = 0
                        """)
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    flash(data2)
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                        SELECT PersonUsername, EventName, Sports, num, SkillLvl
                        FROM (
                        SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                        FROM(
                        SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                        FROM Participants part, Plays play, events event
                        WHERE event.sports = play.SportName AND
                        event.Name = part.EventName AND
                        part.PersonUsername = play.Username
                        ORDER BY EventName, SkillLvl
                        ) a
                        ) t
                        WHERE mod(num, 2) = 1
                        """)
    rows3 = cursor.fetchall()
    data3 = [row for row in rows3]
    cursor.execute("SELECT * FROM Participants")
    rows4 = cursor.fetchall()
    data4 = [row for row in rows4]
    cursor.close()
    #return render_template('my_events.html', data = data, data_friends = data2, data_participates= data3)
    return render_template('my_events.html', data = data, data_team1 = data2, data_team2 = data3, data_participates= data4)

@app.route('/notifications', methods = ['GET','POST'])
def notifications():
    cursor = conn.cursor()
    cursor.execute("""SELECT DISTINCT people.Username, events.name, events.Sports, events.Location, events.Time, events.Creator
                    FROM    people, Plays, PlaysAt, events, Participants
                    WHERE (events.Name = Participants.EventName) AND (people.Username = Plays.Username AND Plays.SportName = events.Sports) AND
                    (PlaysAt.LocationName = events.Location AND people.Username = PlaysAt.Username) AND
                    (events.MaxAge >= people.Age AND events.MinAge <= people.Age) AND
                    (events.MaxSkill >= Plays.SkillLvl AND events.MinSkill <= Plays.SkillLvl) AND
                     (events.Creator <> '{0}')
                    """.format(session['username']))
    rows = cursor.fetchall()
    data = []
    for row in rows:
        if row[0] == session['username']:
            data.append(row)
    cursor.execute('select EventName from Participants where PersonUsername = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row[0] for row in rows2]

    noti_num = len(data2)

    #skip = 0
    cursor.close()
    return render_template('notifications.html', data=data, data2 = data2, noti_num = noti_num)#, skip = skip)

@app.route('/events', methods = ['post', 'get'])
def events():
    #data = ['loc1','loc2','loc3']
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM location')
    rows = cursor.fetchall()
    loc_data = [row for row in rows]
    cursor.execute('SELECT * FROM sports')
    rows2 = cursor.fetchall()
    sports_data = [row for row in rows2]

    sportsQuery = 'Select SportName from Plays Where Username = "' + session['username'] + '";'
    cursor.execute(sportsQuery)

    sportsRows = cursor.fetchall()
    sportsData = [row for row in sportsRows]
    cursor.close()
    return render_template('events.html', loc_data = loc_data, sports_data = sportsData)

@app.route('/friends', methods=['get','post'])
def friends():
    cursor = conn.cursor()
    username = session['username']
    cursor.execute('SELECT * FROM Friends WHERE Username1 = "{0}"'.format(username))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.close()
    return render_template('friends.html',data=data)

@app.route('/update_event', methods = ['post'])
def update_event():
    key = request.form['updateeventname']
    cursor = conn.cursor()
    #SELECT * FROM events WHERE Name LIKE "%hangouSSt%";
    cursor.execute('SELECT * FROM events WHERE Name ="' + key + '"')
    #data = [eventname]
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute('SELECT * FROM location')
    rows2 = cursor.fetchall()
    loc_data = [row for row in rows2]
    cursor.execute('SELECT * FROM sports')
    rows3 = cursor.fetchall()
    sports_data = [row for row in rows3]

    datetime = ('datetime.datetime'+ (str(data[0])).split('datetime')[2]).split(')')[0] + ')'
    #2017-06-01T08:30

    datetime = Search_number_String(datetime)
    datetime = datetime.split(',')

    datetime = [d.strip() for d in datetime]

    if int(datetime[1]) < 10:
        datetime[1] = '0' + datetime[1]
    if int(datetime[2]) < 10:
        datetime[2] = '0' + datetime[2]
    if int(datetime[3]) < 10:
        datetime[3] = '0' + datetime[3]
    if int(datetime[4]) < 10:
        datetime[4] = '0' + datetime[4]

    dateStr = datetime[0] + '-' + datetime[1] + '-' + datetime[2] + 'T' + datetime[3] + ':' + datetime[4]

    cursor.close()

    return render_template('update_events.html', data = data, loc_data = loc_data, sports_data = sports_data, datetime = [dateStr])

def changeDateFormat(date):
	return eval(date).isoformat()[:-3]

def Search_number_String(String):
    index_list = []
    del index_list[:]
    for i, x in enumerate(String):
        if x.isdigit() == True:
            index_list.append(i)
    start = index_list[0]
    end = index_list[-1] + 1
    number = String[start:end]
    return number

@app.route('/search_event', methods = ['post'])
def search_event():
    key = request.form['searchkey']
    cursor = conn.cursor()
    #SELECT * FROM events WHERE Name LIKE "%hangouSSt%";
    cursor.execute('SELECT * FROM events WHERE Name LIKE ' + '"%' + key + '%"')
    #data = [eventname]
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute('select EventName from Participants where PersonUsername = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row[0] for row in rows2]
    # Constraints

    # Playable Sports?

    playsQuery = 'select SportName from Plays where Username = "' + session['username'] + '"'
    cursor.execute(playsQuery)
    playsQueryRows = cursor.fetchall()
    playsQueryData = [row[0] for row in playsQueryRows]

    # In Skill Level Range?

    levelRangeQuery = 'Select SportName, SkillLvl From Plays Where Username = "' + session['username'] + '"'
    cursor.execute(levelRangeQuery)
    levelRangeRows = cursor.fetchall()
    #levelRangeData = [ row for row in levelRangeRows ]
    levelRangeData = { row[0]: row[1] for row in levelRangeRows }
    cursor.close()
    return render_template('live_events.html', data = data, data2 = data2, playsData = playsQueryData, levelData = levelRangeData)

@app.route('/filter_event', methods = ['post'])
def filter_event():
    key = request.form['filter']
    cursor = conn.cursor()
    #SELECT * FROM events WHERE Name LIKE "%hangouSSt%";
    cursor.execute('SELECT * FROM events WHERE Sports = "' + key + '"')
    #data = [eventname]
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute('select EventName from Participants where PersonUsername = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row[0] for row in rows2]
    # Constraints

    # Playable Sports?

    playsQuery = 'select SportName from Plays where Username = "' + session['username'] + '"'
    cursor.execute(playsQuery)
    playsQueryRows = cursor.fetchall()
    playsQueryData = [row[0] for row in playsQueryRows]

    # In Skill Level Range?

    levelRangeQuery = 'Select SportName, SkillLvl From Plays Where Username = "' + session['username'] + '"'
    cursor.execute(levelRangeQuery)
    levelRangeRows = cursor.fetchall()
    #levelRangeData = [ row for row in levelRangeRows ]
    levelRangeData = { row[0]: row[1] for row in levelRangeRows }



    cursor.close()
    return render_template('live_events.html', data = data, data2 = data2, playsData = playsQueryData, levelData = levelRangeData)

@app.route('/leave_event', methods = ['post'])
def leave_event():
    eventName = request.form['nameOfEvent']
    cursor = conn.cursor()
    query = "DELETE FROM Participants WHERE PersonUsername='{0}' AND EventName='{1}'".format(session['username'],eventName)
    cursor.execute(query)
    conn.commit()
    return my_events()

@app.route('/delete_event', methods = ['post'])
def delete_event():
    eventname = request.form['eventname']
    cursor = conn.cursor()
    cursor.execute('DELETE FROM events WHERE Name=' + '"' + eventname + '"')
    conn.commit()
    #data = [eventname]


###############
    cursor.execute("SELECT * FROM events WHERE EXISTS (SELECT PersonUsername FROM Participants WHERE PersonUsername = '{0}' AND Name = EventName) OR Creator = '{0}'".format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                    SELECT PersonUsername, EventName, Sports, num, SkillLvl
                    FROM (
                    SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                    FROM(
                    SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                    FROM Participants part, Plays play, events event
                    WHERE event.sports = play.SportName AND
                    event.Name = part.EventName AND
                    part.PersonUsername = play.Username
                    ORDER BY EventName, SkillLvl
                    ) a
                    ) t
                    WHERE mod(num, 2) = 0
                        """)
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    flash(data2)
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                        SELECT PersonUsername, EventName, Sports, num, SkillLvl
                        FROM (
                        SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                        FROM(
                        SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                        FROM Participants part, Plays play, events event
                        WHERE event.sports = play.SportName AND
                        event.Name = part.EventName AND
                        part.PersonUsername = play.Username
                        ORDER BY EventName, SkillLvl
                        ) a
                        ) t
                        WHERE mod(num, 2) = 1
                        """)
    rows3 = cursor.fetchall()
    data3 = [row for row in rows3]
    cursor.execute("SELECT * FROM Participants")
    rows4 = cursor.fetchall()
    data4 = [row for row in rows4]

    cursor.close()

    return render_template('my_events.html', data = data, data_team1 = data2, data_team2 = data3, data_participates= data4)
##############


@app.route('/delete_sport', methods = ['post'])
def delete_sport():
    sportname = request.form['sportname']
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Plays WHERE SportName=' + '"' + sportname + '"' +  'AND Username="' + session['username'] + '"')
    conn.commit()
    #data = [eventname]
    cursor.execute('SELECT * FROM sports WHERE NOT EXISTS (SELECT Sportname FROM Plays WHERE name = SportName AND Username = "{0}")'.format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute("""SELECT Address, Name FROM location WHERE NOT EXISTS(SELECT LocationName
                        FROM PlaysAt WHERE Address = LocationName and Username = '{0}')""".format(session['username']))
    rows1 = cursor.fetchall()
    loc_data = [row for row in rows1]

    cursor.execute('SELECT Address, Name, OutOrIn FROM location, PlaysAt WHERE Username = "{0}"  AND PlaysAt.LocationName = location.Address'.format(session['username']))
    rows3 = cursor.fetchall()
    my_loc_data = [row for row in rows3]

    cursor.execute('SELECT SportName, SkillLvl FROM Plays WHERE UserName = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    cursor.close()
    return render_template('edit_profile.html', data = data, data2 = data2, loc_data = loc_data, my_loc_data = my_loc_data)

@app.route('/delete_loc', methods = ['post'])
def delete_loc():
    locname = request.form['locname']
    cursor = conn.cursor()
    cursor.execute('DELETE FROM PlaysAt WHERE LocationName=' + '"' + locname + '"' +  'AND Username="' + session['username'] + '"')
    conn.commit()
    #data = [eventname]
    cursor.execute('SELECT * FROM sports WHERE NOT EXISTS (SELECT Sportname FROM Plays WHERE name = SportName AND Username = "{0}")'.format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute("""SELECT Address, Name FROM location WHERE NOT EXISTS(SELECT LocationName
                        FROM PlaysAt WHERE Address = LocationName and Username = '{0}')""".format(session['username']))
    rows1 = cursor.fetchall()
    loc_data = [row for row in rows1]

    cursor.execute('SELECT Address, Name, OutOrIn FROM location, PlaysAt WHERE Username = "{0}"  AND PlaysAt.LocationName = location.Address'.format(session['username']))
    rows3 = cursor.fetchall()
    my_loc_data = [row for row in rows3]

    cursor.execute('SELECT SportName, SkillLvl FROM Plays WHERE UserName = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    cursor.close()
    return render_template('edit_profile.html', data = data, data2 = data2, loc_data = loc_data, my_loc_data = my_loc_data)

@app.route('/events_success', methods = ['post'])
def events_post():
    eventname = request.form['eventname']
    sports = request.form['sports']
    numplayers = int(request.form['numplayers'])
    loc = request.form['location']
    time = request.form['time']
    minage = int(request.form['minage'])
    maxage = int(request.form['maxage'])
    minskill = int(request.form['minskill'])
    maxskill = int(request.form['maxskill'])

    #if request.method == 'POST':
    #    session['logged_in'] = True
    #    session['username'] = request.form['username']

    creator = session['username']

    cursor = conn.cursor()
    #cursor.execute('insert into events values ("' + eventname + ',' + sports  + ',' + numplayers + ',' + loc + ',' + 'NOW()'  + ',' +  minage + ',' + maxage + ',' + minskill + ',' + maxskill + ')')
    query = 'INSERT INTO events VALUES ("{0}", "{1}", {2}, "{3}", "{4}", {5}, {6}, {7}, {8}, "{9}")'.format(eventname, sports, numplayers, loc, time, minage, maxage, minskill, maxskill, creator)

    #query = 'insert into events values("imtestingrightnow3433554", "Basketball", 12, "Peabody Street", 8, 2, 100, 1, 5,"' + creator + '")'
    cursor.execute(query)
    query = 'INSERT INTO Participants VALUES ("{0}","{1}","{2}","{3}")'.format(creator, eventname,loc,creator)
    cursor.execute(query)
    conn.commit()

    data = [eventname, sports, numplayers, loc, minage, maxage, minskill, maxskill, creator]

    cursor.execute("SELECT * FROM events WHERE EXISTS (SELECT PersonUsername FROM Participants WHERE PersonUsername = '{0}' AND Name = EventName) OR Creator = '{0}'".format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                    SELECT PersonUsername, EventName, Sports, num, SkillLvl
                    FROM (
                    SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                    FROM(
                    SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                    FROM Participants part, Plays play, events event
                    WHERE event.sports = play.SportName AND
                    event.Name = part.EventName AND
                    part.PersonUsername = play.Username
                    ORDER BY EventName, SkillLvl
                    ) a
                    ) t
                    WHERE mod(num, 2) = 0
                        """)
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    flash(data2)
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                        SELECT PersonUsername, EventName, Sports, num, SkillLvl
                        FROM (
                        SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                        FROM(
                        SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                        FROM Participants part, Plays play, events event
                        WHERE event.sports = play.SportName AND
                        event.Name = part.EventName AND
                        part.PersonUsername = play.Username
                        ORDER BY EventName, SkillLvl
                        ) a
                        ) t
                        WHERE mod(num, 2) = 1
                        """)
    rows3 = cursor.fetchall()
    data3 = [row for row in rows3]
    cursor.execute("SELECT * FROM Participants")
    rows4 = cursor.fetchall()
    data4 = [row for row in rows4]

    cursor.close()

    return render_template('my_events.html', data = data, data_team1 = data2, data_team2 = data3, data_participates= data4)

""" duplicated but keep it for now
@app.route('/sports', methods = ['post', 'get'])
def sports():
    #data = ['loc1','loc2','loc3']
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sports')
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.close()
    return render_template('edit_profile.html', data = data)
"""

@app.route('/add_sport', methods = ['post'])
def sport_add():
    sportName = request.form['sport']
    skillLevel = int(request.form['skill'])
    creator = session['username']

    cursor = conn.cursor()
    query = 'INSERT INTO Plays VALUES ("{0}", "{1}", {2})'.format(creator, sportName, skillLevel)
    cursor.execute(query)
    conn.commit()
    cursor.execute('SELECT * FROM sports WHERE NOT EXISTS (SELECT Sportname FROM Plays WHERE name = SportName AND Username = "{0}")'.format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute("""SELECT Address, Name FROM location WHERE NOT EXISTS(SELECT LocationName
                        FROM PlaysAt WHERE Address = LocationName and Username = '{0}')""".format(session['username']))
    rows1 = cursor.fetchall()
    loc_data = [row for row in rows1]

    cursor.execute('SELECT Address, Name, OutOrIn FROM location, PlaysAt WHERE Username = "{0}"  AND PlaysAt.LocationName = location.Address'.format(session['username']))
    rows3 = cursor.fetchall()
    my_loc_data = [row for row in rows3]

    cursor.execute('SELECT SportName, SkillLvl FROM Plays WHERE UserName = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2= [row for row in rows2]
    cursor.close()
    return render_template('edit_profile.html', data = data, data2 = data2, loc_data = loc_data, my_loc_data = my_loc_data)

@app.route('/add_location', methods = ['post'])
def add_location():
    locationName = request.form['location']
    creator = session['username']

    cursor = conn.cursor()
    query = 'INSERT INTO PlaysAt VALUES ("{0}", "{1}")'.format(locationName, creator)

    cursor.execute(query)
    conn.commit()

    cursor.execute('SELECT * FROM sports WHERE NOT EXISTS (SELECT Sportname FROM Plays WHERE name = SportName AND Username = "{0}")'.format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute("""SELECT Address, Name FROM location WHERE NOT EXISTS(SELECT LocationName
                        FROM PlaysAt WHERE Address = LocationName and Username = '{0}')""".format(session['username']))
    rows1 = cursor.fetchall()
    loc_data = [row for row in rows1]

    cursor.execute('SELECT Address, Name, OutOrIn FROM location, PlaysAt WHERE Username = "{0}"  AND PlaysAt.LocationName = location.Address'.format(session['username']))
    rows3 = cursor.fetchall()
    my_loc_data = [row for row in rows3]

    cursor.execute('SELECT SportName, SkillLvl FROM Plays WHERE UserName = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2= [row for row in rows2]
    cursor.close()
    return render_template('edit_profile.html', data = data, data2 = data2, loc_data = loc_data, my_loc_data = my_loc_data)

@app.route('/events_update', methods = ['post'])
def events_update():

    eventname = request.form['eventname']
    sports = request.form['sports']
    numplayers = int(request.form['numplayers'])
    loc = request.form['location']
    time = request.form['time']
    minage = int(request.form['minage'])
    maxage = int(request.form['maxage'])
    minskill = int(request.form['minskill'])
    maxskill = int(request.form['maxskill'])

    creator = session['username']

    cursor = conn.cursor()
    query = 'UPDATE events SET Sports="{0}", NumPlayers={1}, Location="{2}", Time="{3}", MinAge={4}, MaxAge = {5}, MinSkill={6}, MaxSkill={7} WHERE Name="{8}"'.format(sports, numplayers, loc, time, minage, maxage, minskill, maxskill, eventname)
    cursor.execute(query)
    conn.commit()
    cursor.execute("SELECT * FROM events")
    rows = cursor.fetchall()
    changedData = [row for row in rows]


    cursor.execute("SELECT * FROM events WHERE EXISTS (SELECT PersonUsername FROM Participants WHERE PersonUsername = '{0}' AND Name = EventName) OR Creator = '{0}'".format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                    SELECT PersonUsername, EventName, Sports, num, SkillLvl
                    FROM (
                    SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                    FROM(
                    SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                    FROM Participants part, Plays play, events event
                    WHERE event.sports = play.SportName AND
                    event.Name = part.EventName AND
                    part.PersonUsername = play.Username
                    ORDER BY EventName, SkillLvl
                    ) a
                    ) t
                    WHERE mod(num, 2) = 0
                        """)
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    flash(data2)
    cursor.execute('SET @row_number = 0')
    cursor.execute("""
                        SELECT PersonUsername, EventName, Sports, num, SkillLvl
                        FROM (
                        SELECT (@row_number:=@row_number+1) as num, PersonUsername, EventName, Sports, SkillLvl
                        FROM(
                        SELECT part.PersonUsername, part.EventName, event.Sports, play.SkillLvl
                        FROM Participants part, Plays play, events event
                        WHERE event.sports = play.SportName AND
                        event.Name = part.EventName AND
                        part.PersonUsername = play.Username
                        ORDER BY EventName, SkillLvl
                        ) a
                        ) t
                        WHERE mod(num, 2) = 1
                        """)
    rows3 = cursor.fetchall()
    data3 = [row for row in rows3]
    cursor.execute("SELECT * FROM Participants")
    rows4 = cursor.fetchall()
    data4 = [row for row in rows4]

    cursor.close()

    return render_template('my_events.html', changedData = changedData, data = data, data_team1 = data2, data_team2 = data3, data_participates= data4)


@app.route('/welcome')
def welcome():
	return render_template('welcome.html')

def login_required(test):
	@wraps(test)
	def wrap(*args, **kwargs):
		if 'logged_in' in session:
			return test(*args, **kwargs)
		else:
			flash('You need to login first.')
			return redirect(url_for('log'))
	return wrap

@app.route('/hello')
@login_required
def hello():
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sports")
    rows = cursor.fetchall()
    data = [row for row in rows]
    cursor.close()
    return render_template('hello.html', data = data)

@app.route('/logout')
def logout():
	session.pop('logged_in', None)
	flash('You were logged out')
	return redirect (url_for('home'))

@app.route('/edit_profile')
def edit_profile():
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sports WHERE NOT EXISTS (SELECT Sportname FROM Plays WHERE name = SportName AND Username = "{0}")'.format(session['username']))
    rows = cursor.fetchall()
    data = [row for row in rows]

    cursor.execute("""SELECT Address, Name FROM location WHERE NOT EXISTS(SELECT LocationName
                        FROM PlaysAt WHERE Address = LocationName and Username = '{0}')""".format(session['username']))
    rows1 = cursor.fetchall()
    loc_data = [row for row in rows1]

    cursor.execute('SELECT Address, Name, OutOrIn FROM location, PlaysAt WHERE Username = "{0}"  AND PlaysAt.LocationName = location.Address'.format(session['username']))
    rows3 = cursor.fetchall()
    my_loc_data = [row for row in rows3]

    cursor.execute('SELECT SportName, SkillLvl FROM Plays WHERE Username = "{0}"'.format(session['username']))
    rows2 = cursor.fetchall()
    data2 = [row for row in rows2]
    cursor.close()
    return render_template('edit_profile.html', data = data, data2 = data2, loc_data = loc_data, my_loc_data = my_loc_data)

@app.route('/reg', methods = ['GET', 'POST'])
def register():
    try:
        form = RegistrationForm(request.form)

        if request.method == "POST" and form.validate():
            flash("Validated")
            username = form.username.data
            password = form.password.data
            name = form.real_name.data
            age = form.age.data
            c = conn.cursor()

            x = c.execute("SELECT * FROM people WHERE username = '{0}'".format(username))

            if int(x) > 0:
                flash("THAT USER NAME IS ALREADY TAKEN REEEEEEEEEEEEEEEEEEEEEEEEE")
                return render_template('register.html',form=form)

            else:
                query = "INSERT INTO people (Username,Name,Age,Password) VALUES ('{0}','{1}','{2}','{3}')".format(username,name,age,password)
                c.execute(query)
                conn.commit()

                c.close()
                conn.close()
                gc.collect()

                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for("home"))
        flash("Invalidated")
        return render_template("register.html",form=form)

    except Exception as e:
        error=str(e)
        return render_template("register.html", error=error)

@app.route('/log', methods = ['GET', 'POST'])
def log():
    error = "No Error"
    try:
        c = conn.cursor()
        if request.method == 'POST':

            data = c.execute("SELECT * FROM people WHERE username='{0}'".format(request.form['username']))
            data = c.fetchone()[3] # username, password

            if request.form['password'] == data:
                session['logged_in'] = True
                session['username'] = request.form['username']

                flash("you are now logged in")
                return redirect(url_for("home"))
            else:
                error = "invalid creds"
        gc.collect()
        return render_template('log.html', error=error)

    except Exception as e:
        error=str(e)
        return render_template("log.html", error=error)






if __name__ == '__main__':
    #app.debug = True
    socketio.run(app, debug=True)
    #app.run()
