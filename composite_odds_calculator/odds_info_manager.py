import mysql.connector
from datetime import datetime, timedelta
import threading
import os
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class OddsInfo:
    def __init__(self, field_code, race_number, deadline_time, odds_refresh_time, odds_json):
        self.field_code = field_code
        self.race_number = race_number
        self.deadline_time = deadline_time
        self.odds_refresh_time = odds_refresh_time
        self.odds_json = odds_json


class OddsInfoManager:
    def __init__(self):
        self.odds_infos = []
        self.is_fetched_once = threading.Event()
        self.run_flag = None
        self.cv = threading.Condition()
        self.lock = threading.Lock()
        self.thread = None
        self.cursor = None
        self.conn = None

    def get_odds_infos(self):
        self.is_fetched_once.wait() # 1度fetchが完了するまで待機、それ以降はこのwaitは機能しない
        with self.lock:
            return self.odds_infos.copy()
        

    def fetch_odds(self, cursor, date):
        # 当日の各レース場の最新レコードで未確定オッズのレース情報をDBから取得
        query = f"""\
        SELECT t1.* FROM odds t1 \
        INNER JOIN (SELECT field_code, MAX(created_at) AS max_created_at FROM odds \
        WHERE race_date = '{date}' GROUP BY field_code) t2 \
        ON t1.field_code = t2.field_code AND t1.created_at = t2.max_created_at;\
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        races = []
        
        for row in rows:
            races.append(OddsInfo(row[1], row[2], row[3], row[4], row[6]))
            logging.info(f"Fetch Result=[race_date:{row[0]}, field_code:{row[1]}, race_number:{row[2]}, deadline_time:{row[3]}, odds_refresh_time:{row[4]}, created_at:{row[5]}]")
            
        if len(races) == 0:
            logging.warning("Fetch Result: No record found.")

        with self.lock:
            self.odds_infos = races
            self.is_fetched_once.set()

    def fetch_odds_thread(self, run_flag, cursor):
        datetime_now = datetime.utcnow() + timedelta(hours=9)
        date = datetime_now.date().strftime('%Y%m%d')

        while run_flag.is_set():
            self.fetch_odds(cursor, date)
            with self.cv:
                self.cv.wait(60)

    def start(self):
        self.conn = mysql.connector.connect(
            host=os.environ['RDS_HOST_NAME'],
            port='3306',
            user=os.environ['USER'],
            password=os.environ['PASS'],
            database=os.environ['DB_NAME']
        )
        self.cursor = self.conn.cursor()

        self.run_flag = threading.Event()
        self.run_flag.set()
        self.thread = threading.Thread(target=self.fetch_odds_thread, args=(self.run_flag, self.cursor))
        self.thread.start()

    def stop(self):
        self.run_flag.clear()
        with self.cv:
            self.cv.notify()
        self.thread.join()
        self.cursor.close()
        self.conn.close()

