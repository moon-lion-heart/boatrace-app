import json
import mysql.connector
from datetime import datetime, timedelta
import time
import threading
import os
import argparse
from dotenv import load_dotenv
load_dotenv()

"""
必要な機能：
DB操作
CUIインターフェース
合成オッズ計算
起動オプション
"""

STATUS_DEADLINE = "" # これはあとで共通定義ファイルを作って参照するようにしたい
    
class Combination:
    def __init__(self, combination, odds):
        self.combination = combination
        self.odds = odds

class OddsInfo:
    def __init__(self, field_code, race_number, odds_refresh_time, odds_json):
        self.field_code = field_code
        self.race_number = race_number
        self.odds_refresh_time = odds_refresh_time
        self.odds_json = odds_json

class OddsInfoManager:
    def __init__(self):
        self.odds_infos = [] #これはタプルにするかcopyで渡したほうがよさげ
        self.is_updated_odds_infos = False
        self.is_fetched_once = threading.Event()
        self.run_flag = None
        self.lock = threading.Lock()
        self.thread = None
        self.cursor = None
        self.conn = None


    def get_odds_infos(self):
        self.is_fetched_once.wait() # 1度fetchが完了するまで待機、それ以降はこのwaitは機能しない
        with self.lock:
            self.is_updated_odds_infos = False
            return self.odds_infos.copy()
        

    def fetch_odds(self, cursor, date):
        # 当日の各レース場の最新レコードで未確定オッズのレース情報をDBから取得
        query = f"""\
        SELECT t1.* FROM odds t1 \
        INNER JOIN (SELECT field_code, MAX(created_at) AS max_created_at FROM odds \
        WHERE race_date = '{date}' AND odds_refresh_time != '{STATUS_DEADLINE}' GROUP BY field_code) t2 \
        ON t1.field_code = t2.field_code AND t1.created_at = t2.max_created_at;\
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        races = []
        
        for row in rows:
            races.append(OddsInfo(row[1], row[2], row[3], row[5]))
            print(f"Fetch Result=[race_date:{row[0]}, field_code:{row[1]}, race_number:{row[2]}, odds_refresh_time:{row[3]}, created_at:{row[4]}, odds:{row[5]}]")
            
        if len(races) == 0:
            print("Fetch Result: No record found.") # CUIクライアントの場合は標準出力ではなくログに出したほうがいいかも

        with self.lock:
            self.odds_infos = races
            self.is_updated_odds_infos = True
            self.is_fetched_once.set()


    def fetch_odds_thread(self, run_flag, cursor):
        datetime_now = datetime.utcnow() + timedelta(hours=9)
        date = datetime_now.date().strftime('%Y%m%d')

        while run_flag.is_set():
            self.fetch_odds(cursor, date)
            time.sleep(60) # ここは単純なsleepではなく排他制御用のsleepがあると思うからそれを使う。


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
        thread = threading.Thread(target=self.fetch_odds_thread, args=(self.run_flag, self.cursor))
        thread.start()


    def stop(self):
        self.run_flag.clear()
        self.thread.join()
        self.cursor.close()
        self.conn.close()



def culc_betting_amount(total_betting_amount, composite_odds, odds, betting_selection):
    betting_amount = total_betting_amount * composite_odds / odds
    betting_amount = int(round(betting_amount / 100) * 100)
    estimated_refund_amount = int(betting_amount * odds)
    print(f"買い目：{betting_selection}, 賭け額：{betting_amount}円, 払い戻し額：{estimated_refund_amount}円")
    
    return betting_amount


# 引数は買い目とオッズのペアのリスト、戻り値はなしで標準出力に結果を出力
def calc_composite_odds(betting_amount, combinations):
    sum_odds = 0
    for i in range(len(combinations)):
        sum_odds += 1 / float(combinations[i][1])
    composite_odds = 1 / sum_odds
    print(f"合成オッズ：{composite_odds}")
    
    sum_betting_amount = 0
    for i in range(len(combinations)):
        odds = float(combinations[i][1])
        betting_selection = combinations[i][0]
        betting_amount = culc_betting_amount(betting_amount, composite_odds, odds, betting_selection)
        sum_betting_amount += betting_amount

    print(f"合計賭け額:{sum_betting_amount}円")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='合成オッズ計算機')
    parser.add_argument("-b", type=int, default=10000, help="賭け額, default=10000")
    args = parser.parse_args()
    
    betting_amount = args.b

    # 別スレッドで1分おきにDBから最新のレース情報を取得する
    # 取得するのは当日各レース場の最新のレース情報だけ
    # 次のレースが締め切り10分前になるまでは直前の締め切られたレースの確定オッズで合成オッズを計算できる
    odds_info_manager = OddsInfoManager()
    odds_info_manager.start()
    odds_infos = None
    while True:
        # 最新のレース情報を表示(レース場、ラウンド)
        odds_infos = odds_info_manager.get_odds_infos()
        print(f"")
        # 買い目毎のオッズを出力するためにどのレースのオッズを見るか選択してもらう
        # オッズ一覧表示
        # 合成オッズ計算のための買い目を複数選択してもらう
        # 合成オッズを計算し出力する
        # 合成オッズ計算のための買い目を複数選択してもらう、または別のレース選択画面に移る
        input_value = input()
        if input_value == "q":
            break

    odds_info_manager.stop()