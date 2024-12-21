import json
from bs4 import BeautifulSoup
import mysql.connector
from datetime import datetime, timedelta
import time
import os
import re
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class RaceInfo:
    def __init__(self, field_code, race_number, deadline_time=None, odds_refresh_time=None):
        self.field_code = field_code
        self.race_number = race_number
        self.deadline_time = deadline_time
        self.odds_refresh_time = odds_refresh_time

STATUS_DEADLINE = ""
DEADLINE_M = int(os.environ['DEADLINE_M'])
SLEEP_TIME_S = float(os.environ['SLEEP_TIME_S'])
REQUEST_TIMEOUT_S = float(os.environ['REQUEST_TIMEOUT_S'])
HEADERS = {
    "accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding":"gzip, deflate, br, zstd",
    "accept-language":"ja,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
    "priority":"u=0, i",
    "sec-ch-ua":'"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
    "sec-ch-ua-mobile":"?0",
    "sec-ch-ua-platform":"Windows",
    "sec-fetch-dest":"document",
    "sec-fetch-mode":"navigate",
    "sec-fetch-site":"none",
    "sec-fetch-user":"?1",
    "upgrade-insecure-requests":"1",
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
}

def lambda_handler(event, context):
    run()
    
    return {
        'statusCode': 200,
        'body': json.dumps('Done!')
    }


def run():
    session = requests.Session()
    session.headers.update(HEADERS)

    conn = mysql.connector.connect(
        host=os.environ['RDS_HOST_NAME'],
        port='3306',
        user=os.environ['USER'],
        password=os.environ['PASS'],
        database=os.environ['DB_NAME']
    )
    cursor = conn.cursor()

    datetime_now = datetime.utcnow() + timedelta(hours=9)
    datetime_now_str = datetime_now.strftime('%Y-%m-%d %H:%M:%S')
    date = datetime_now.date().strftime('%Y%m%d')

    # 本日のレース一覧から締め切り10分前以内のレース情報を取得する
    index_races = scrape_index(session, date)
    # 当日の各レース場の最新レコードで未確定オッズのレース情報をDBから取得
    unfixed_odds_races = fetch_race_info(cursor, date)
    # 締め切り１０分前のレースと最新の締め切られたレースのみオッズを取得する
    races = []
    for unfixed_odds_race in unfixed_odds_races:
        needs_append = True
        for index_race in index_races:
            if unfixed_odds_race.field_code == index_race.field_code:
                index_race.odds_refresh_time = unfixed_odds_race.odds_refresh_time
                needs_append = False
                break
        if needs_append:
            races.append(unfixed_odds_race)
    races.extend(index_races)

    if len(races) == 0:
        print("No races found that meet the conditions for getting odds info.")
        return

    print("Get started scraping odds info.")
    combinations = create_combinations()
    odds_tables = []
    for race in races:
        field_code = race.field_code
        race_number = race.race_number
        try:      
            # 3連単
            url = create_url("odds3t", race_number, field_code, date)
            trifecta_odds, refresh_time = scrape_odds(session, url)
            if len(trifecta_odds) == 0:
                print("Failed to get trifecta odds info.")
                continue

            # 前回取得時と同じオッズ更新時間の場合レコードには追加しない
            print(f"refresh_time: {refresh_time}, race.odds_refresh_time: {race.odds_refresh_time}")
            if refresh_time == race.odds_refresh_time:
                print("No updates to the trifecta odds info")
                continue
            
            # 3連複
            url = create_url("odds3f", race_number, field_code, date)
            trio_odds, refresh_time = scrape_odds(session, url)
            if len(trio_odds) == 0:
                print("Failed to get trio odds info.")
                continue

            trifecta_odds_dict = dict(zip(combinations["3t"], trifecta_odds))
            trio_odds_dict = dict(zip(combinations["3f"], trio_odds))
            odds_dict = {"3t": trifecta_odds_dict, "3f": trio_odds_dict}
            odds_json = json.dumps(odds_dict)
            odds_table = [date, field_code, race_number, race.deadline_time, refresh_time, datetime_now_str]
            odds_table.append(odds_json)
            odds_tables.append(odds_table)
        except Exception as e:
            print(f"Error: {e}")

    if len(odds_tables) > 0:
        # insert
        query = """\
        INSERT INTO odds (race_date, field_code, race_number, deadline_time, odds_refresh_time, created_at, odds) \
        VALUES (%s, %s, %s, %s, %s, %s, %s)\
        """
        cursor.executemany(query, odds_tables)
        conn.commit()
        print(f"{len(odds_tables)} records inserted.")

    cursor.close()
    conn.close()


def scrape_index(session, date):
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date}"
    races = []
    current_time = datetime.utcnow() + timedelta(hours=9)

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_S)
        if response.status_code != 200:
            print(f"Session get error. status_code:{response.status_code}")
            return races
            
        soup = BeautifulSoup(response.text, 'html.parser')
        table1 = soup.find('div', class_='table1')
        tbodies = table1.find_all('tbody')
        for tbody in tbodies:
            tds = tbody.find_all('td')
            if len(tds) != 12: # 最終Ｒ発売終了
                # print("Final round of sales is closed.")
                continue
            
            #現在時刻よりも締め切り時間が指定時間以上あとかどうか
            deadline_time_str = tds[len(tds)-1].get_text()
            deadline_time = datetime.strptime(deadline_time_str, "%H:%M")
            deadline_time = datetime.combine(current_time.date(), deadline_time.time())
            time_difference = deadline_time - current_time
            if abs(time_difference) > timedelta(minutes=DEADLINE_M):
                # print(f"It is more than {DEADLINE_M} minutes before the deadline.:{deadline_time}")
                continue

            # get next race number
            race_number = tds[2].get_text()
            race_number = race_number.replace('R', '')
            if not race_number.isnumeric():
                print("Failed to get race number in race index page.")
                continue
            
            # get field code
            title = tbody.find(class_='is-alignL is-fBold is-p10-7')
            a_tag = title.find("a")
            href = a_tag.get('href')
            if len(href) < 30:
                print("Failed to get field code in race index page.")
                continue
            field_code = href[28:30]

            races.append(RaceInfo(field_code, race_number, deadline_time_str))
    
        return races
    except Exception as e:
        print(f"Error: {e}")
        return races


def scrape_odds(session, url):
    odds_list = []

    response = session.get(url, timeout=REQUEST_TIMEOUT_S)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tbody = soup.find('tbody', class_='is-p3-0')
        if tbody == None:
            print("The race has been canceled.")
            return odds_list
        oddsPoints = tbody.find_all('td', class_="oddsPoint")

        for oddsPoint in oddsPoints:
            odds_list.append(oddsPoint.get_text())

        #オッズ更新時間または締め切り状態を取得する
        tab4_refreshText = soup.find('p', class_='tab4_refreshText')
        if tab4_refreshText:
            tab4_text = tab4_refreshText.get_text()
            refresh_time = re.sub(r"\s|[ぁ-んァ-ン一-龥々\s]", "", tab4_text)
        else:
            refresh_time = STATUS_DEADLINE
    else:
        print(f"Session get error. status_code:{response.status_code}")
        print(url)

    time.sleep(SLEEP_TIME_S)
    return odds_list, refresh_time


def fetch_race_info(cursor, date):
    # 当日の各レース場の最新レコードで未確定オッズのレース情報をDBから取得
    query = f"""\
    SELECT t1.race_date, t1.field_code, t1.race_number, t1.deadline_time, t1.odds_refresh_time, t1.created_at FROM odds t1 \
    INNER JOIN (SELECT field_code, MAX(created_at) AS max_created_at FROM odds \
    WHERE race_date = '{date}' AND odds_refresh_time != '{STATUS_DEADLINE}' GROUP BY field_code) t2 \
    ON t1.field_code = t2.field_code AND t1.created_at = t2.max_created_at;\
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    races = []
    
    for row in rows:
        races.append(RaceInfo(row[1], row[2], row[3], row[4]))
        print(f"Fetch Result=[race_date:{row[0]}, ",end="")
        print(f"field_code:{row[1]}, ",end="")
        print(f"race_number:{row[2]}, ",end="")
        print(f"deadline_time:{row[3]}, ",end="")
        print(f"odds_refresh_time:{row[4]}, ",end="")
        print(f"created_at:{row[5]}")
        
    if len(races) == 0:
        print("Fetch Result: No record found.")

    return races


def create_combinations():
    combinations_for_each_type = {}
    # 3連単
    combinations = []
    for second in range(2, 7):
        increment_flag = False
        for third in range(2, 6):
            tmp_second = second
            if tmp_second == third:
                increment_flag = True
            if increment_flag == True:
                third+=1
            
            for first in range (1,7):
                if first == tmp_second:
                    tmp_second -= 1
                if first == third:
                    third -= 1
                combination = f"{first}-{tmp_second}-{third}"
                combinations.append(combination)
    combinations_for_each_type["3t"] = combinations
    # 3連複
    combinations = []
    for second in range(2, 6):
        for third in range(second+1, 7):
            for first in range (1, second):
                combination = f"{first}={second}={third}"
                combinations.append(combination)
    combinations_for_each_type["3f"] = combinations

    return combinations_for_each_type


def create_url(category, race_no, field_code, date):
    url = f"https://www.boatrace.jp/owpc/pc/race/{category}?rno={race_no}&jcd={field_code}&hd={date}"
    print(url)  
    return url
