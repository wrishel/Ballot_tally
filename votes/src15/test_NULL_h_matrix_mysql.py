import mysql.connector
from mysql.connector import errorcode
import time
import json
import numpy as np

if __name__ == "__main__":

    try:
        cnx = mysql.connector.connect(user='election',password='election', database='election')
    except mysql.connector.Error as err:
        exit()

    cursor = cnx.cursor(prepared=False)

    #create a fake ballot record with real and with null H_matrix
    result_as_dict = {}
    
    h_matrix_real = np.ones( (3,3), dtype=np.float )
    h_matrix_none = None

    result_as_dict['h_matrix_real'] = json.dumps(h_matrix_real.tolist())
    result_as_dict['h_matrix_none'] = h_matrix_none

    #delete any previous test records

    cursor.execute("delete from election.images where image_number = 999999") #used for real valued h_matrix
    cursor.execute("delete from election.images where image_number = 999998") #used for None h_matrix

    insert_h_matrix_values = []

    #using a fake image_number ('999999') insert the real matrix into the comments column (since it's a VARCHAR)
    #  and insert the None matrix into comments column of 999998
    insert_h_matrix_sql = "INSERT into election.images (image_number, comments) values (%s, %s)"
    
    #prepare the data for insertion into DB - YOU MUST CHECK FOR NONE as flag that matrix does not exist for this ballot form!!
    image_number = 999999
    matrix_data = result_as_dict.get('h_matrix_real')

    insert_h_matrix_values.append( (image_number, matrix_data) )

    #prepare the data for insertion into DB - YOU MUST CHECK FOR NONE as flag that matrix does not exist for this ballot form!!
    image_number = 999998
    matrix_data = result_as_dict.get('h_matrix_none')
    
    insert_h_matrix_values.append( (image_number, matrix_data) )

    cursor.executemany(insert_h_matrix_sql, insert_h_matrix_values)

    cnx.commit()

    #now select both types back out and reconstruct h_matrix

    cursor.execute("select comments from election.images where image_number = 999999")
    result = cursor.fetchone()
    print(f"real h_matrix query from comments column = {result}")
    #convert to numpy array
    real_valued_h_matrix = np.array(json.loads(result[0]), dtype=np.float)
    print(f"resulting real valued numpy matrix = {real_valued_h_matrix}")

    cursor.execute("select comments from election.images where image_number = 999998")
    result = cursor.fetchone()
    print(f"None h_matrix query from comments column = {result}")
    #convert to numpy array
    real_valued_h_matrix = np.array(json.loads(result[0]), dtype=np.float)
    print(f"resulting real valued numpy matrix = {real_valued_h_matrix}")
