import MySQLdb

conn = MySQLdb.connect('GucciGang5.mysql.pythonanywhere-services.com', 'GucciGang5', 'cs411cs411', \
        'GucciGang5$guccigang')

c = conn.cursor()

c.execute('SELECT * FROM sports')

rows = c.fetchall()

for each in rows:
    print(each)

c.close()