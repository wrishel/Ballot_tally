import sys
import mysql.connector as dbase
from mysql.connector.constants import ClientFlag

db_credentials = {
    "user": "ETP",
    "password": "Hetp2020",
    "database": "HETPtesting"
}

class ETPdb():
    """Interface to MySQL database.

       As a general rule, rows are returned as namedtuples."""

    def __init__(self):
        self.tracing_sql = False
        self.connect()

    def connect(self):
        """Create connection.

           db_choice says whether to use the test or production database"""
        self.tracing_sql = True
        self.cnx = dbase.connect(**db_credentials)

    # -------------------------------  Server interactions  -------------------------------

    def exe(self, sql, indata=None, multi=False, commit=False):
        """Execute sql with no return values."""

        if self.tracing_sql:
            print(sql)
            if indata:
                print(indata)
        cursor = self.cnx.cursor(named_tuple=True)
        if indata:
            ret = cursor.execute(sql, indata, multi)
        else:
            ret = cursor.execute(sql)
        cursor.close()
        if commit:
            self.cnx.commit()
        return ret

    def exe_many(self, sql, indata):
        """Execute sql using indata and commit."""

        if self.tracing_sql:
            print(sql)
            print(indata)
        cursor = self.cnx.cursor(named_tuple=True)
        ret = cursor.executemany(sql, indata)
        cursor.close()
        self.cnx.commit()
        return ret

    def exe_script(self, sqliter):
        """Execute a sequence of lines from sqliter. Always commits at the end."""

        cursor = self.cnx.cursor()
        for s in sqliter.split('\n'):
            if self.tracing_sql:
                print(s)
            ret = cursor.execute(s)

        cursor.close()
        self.cnx.commit()

    def retrieve(self, sql):
        """Execute sql and return list of named tuples."""

        if self.tracing_sql:
            print(sql)
        cursor = self.cnx.cursor(named_tuple=True)
        try:
            cursor.execute(sql)
        except Exception as e:
            print(f'exception in retrieve{e}, sql={sql}')
            raise e
        res = cursor.fetchall()
        cursor.close()
        return res


