# import psycopg2, os
# from psycopg2 import pool
# from dotenv import load_dotenv

# # 引用環境參數
# load_dotenv()

# class Sqlmethod:
#     def __init__(self):
#         self.host = os.getenv("dbhost")
#         self.port = os.getenv("dbport")
#         self.database = os.getenv("psdatabase")
#         self.user = os.getenv("dbuser")
#         self.password = os.getenv("dbpassword")
#         # 建立 connection pool
#         try:
#             self.postgreSQL_pool = psycopg2.pool.SimpleConnectionPool(1,20, user=self.user, password=self.password, host=self.host, port=self.port, database=self.database)
#         except (Exception, psycopg2.DatabaseError) as error:
#             print("Error while connecting to PostgreSQL", error)

#     def get_connecitonpool(self):
#         return self.postgreSQL_pool

#     def __del__(self):
#         if self.postgreSQL_pool:
#             self.postgreSQL_pool.closeall
            
# psSQL = Sqlmethod()