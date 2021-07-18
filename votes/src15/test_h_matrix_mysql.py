import mysql.connector
from mysql.connector import errorcode
import time
import json
import numpy as np

if __name__ == "__main__":

    try:
        cnx = mysql.connector.connect(user='election',password='election', database='election')
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
            exit()
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
            exit()
        else:
            print(err)
            exit()

    cursor = cnx.cursor(prepared=False)

    #create a real h_matrix and a None h_matrix

    real_h_matrix = np.ones((3,3),dtype=np.float)
    none_h_matrix = None

    real_h_matrix_as_json = json.dumps(real_h_matrix.tolist())
    none_h_matrix_as_json = json.dumps(none_h_matrix)  #can't do a None.tolist() !

    print(f"real h matrix as json string = {real_h_matrix_as_json}")
    print(f"none h matrix as json string = {none_h_matrix_as_json}")  #NOTE - this is "null" not ""

    #delete any previous test records

    cursor.execute("delete from election.images where image_number = 999999")
    cursor.execute("delete from election.images where image_number = 999998")

    insert_values = []

    #using a fake image_number ('999999') insert the real matrix into the real json column (H_matrix)
    #  and insert the same json string into the "comments" column as a plain string

    insert_test_h_matrix = "INSERT into election.images (image_number, H_matrix, comments, processing_comment) values (%s, %s, %s, %s)"
    insert_values.append( (999999, real_h_matrix_as_json, real_h_matrix_as_json, "") )

    #using a different fake image_number ('999998') insert the NONE matrix into the real json column (H_matrix)
    #  and insert the same NONE json string into the "comments" column as a plain string

    insert_values.append( (999998, none_h_matrix_as_json, none_h_matrix_as_json, "") )

    cursor.executemany(insert_test_h_matrix, insert_values)

    cnx.commit()

    #now select both types back out and reconstruct h_matrix
    #select from the json column
    cursor.execute("select h_matrix from election.images where image_number = 999999")
    result = cursor.fetchone()
    print(f"h_matrix query from json column = {result}")
    #convert to numpy
    json_column_h_matrix = np.array(result[0])
    print(f"resulting numpy matrix = {json_column_h_matrix}")

    #NOW select from the VARCHAR column
    cursor.execute("select comments from election.images where image_number = 999999")
    result = cursor.fetchone()
    print(f"h_matrix query from COMMENTS column = {result}")
    #convert to numpy
    varchar_column_h_matrix = np.array(result[0])
    print(f"resulting numpy matrix = {varchar_column_h_matrix}")

    #select the null matrix from the json column
    cursor.execute("select h_matrix from election.images where image_number = 999998")
    result = cursor.fetchone()
    print(f"NULL h_matrix query from json column = {result}")
    #convert to python
    data = json.loads(result[0])
    print(f"NULL h_matrix from json column, converted to python = {data}")
    #convert to numpy
    #json_column_h_matrix = np.array(result[0])
    #print(f"resulting numpy matrix = {json_column_h_matrix}")

    #select the null matrix from the varchar column
    cursor.execute("select h_matrix from election.images where image_number = 999998")
    result = cursor.fetchone()
    print(f"VARCHAR h_matrix query from json column = {result}")
    data2 = json.loads(result[0])
    print(f"NULL h_matrix from json column, converted to python = {data2}")
    print("done")