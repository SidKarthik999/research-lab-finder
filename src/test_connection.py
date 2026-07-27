from database import get_connection, get_all_institutions

connection = get_connection()

institutions = get_all_institutions()

for institution in institutions:
    print(institution)