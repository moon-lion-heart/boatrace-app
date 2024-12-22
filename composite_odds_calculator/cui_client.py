import json
import argparse
import logging
import os
from datetime import datetime
from odds_info_manager import OddsInfoManager
from color import Colorize


# この辺は共通定義ファイルを作ってそこに集めたい気持ちがある
FIELD_CODE_MAP = {
    "01":"桐生",
    "02":"戸田",
    "03":"江戸川",
    "04":"平和島",
    "05":"多摩川",
    "06":"浜名湖",
    "07":"蒲郡",
    "08":"常滑",
    "09":"津",
    "10":"三国",
    "11":"びわこ",
    "12":"住之江",
    "13":"尼崎",
    "14":"鳴門",
    "15":"丸亀",
    "16":"児島",
    "17":"宮島",
    "18":"徳山",
    "19":"下関",
    "20":"若松",
    "21":"芦屋",
    "22":"福岡",
    "23":"唐津",
    "24":"大村"
}

STATUS_DEADLINE = ""

SECTION_CHOIE_RACE = 0
SECTION_DISPLAY_ODDS = 1
SECTION_CALCULATE_ODDS = 2

TRIFECTA = "3t"
TRIO = "3f"

COMBINATION_CHARACTERS = {
    TRIFECTA: "3連単",
    TRIO: "3連複"
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="composite_odds_calculator.log",
    filemode="a"  # "a"は追記モード, "w"にすると上書きモード
)

    
class Combination:
    def __init__(self, combination, odds):
        self.combination = combination
        self.odds = odds


class CUIClient:
    def __init__(self, betting_amount, odds_per_line):
        self.odds_infos = None
        self.odds_dict = None
        self.entered_field_code = None
        self.section = SECTION_CHOIE_RACE
        self.combination_type = TRIFECTA
        self.odds_per_line = odds_per_line
        self.betting_amount = betting_amount
    
    def get_section(self):
        return self.section
    
    def section_choice_race(self, odds_infos):
        self.odds_infos = odds_infos
        for odds_info in self.odds_infos:
            deadline_time = datetime.strptime(odds_info.deadline_time, "%H:%M").time()
            current_time = datetime.now().time()
            deadline_time_str = odds_info.deadline_time if deadline_time >= current_time else "締切済"
            print(f"ID：{odds_info.field_code}", end=" ")
            print(f"レース場：{FIELD_CODE_MAP[odds_info.field_code]}, ", end=" ")
            print(f"レース：{odds_info.race_number}, ", end=" ")
            print(f"締め切り時間：{deadline_time_str}")

        enter = input("q:プログラムを終了する\nIDを入力してください：")
        if enter == "q":
            return False
        self.entered_field_code = enter
        self.section = SECTION_DISPLAY_ODDS
        return True
        
    def section_display_odds(self):
        # オッズ一覧表示（デフォルトは3連単）
        is_valid_enter = False
        for odds_info in self.odds_infos:
            if odds_info.field_code == self.entered_field_code:
                is_valid_enter = True
                print(f"レース場：{FIELD_CODE_MAP[odds_info.field_code]}, ", end=" ")
                print(f"レース：{odds_info.race_number}, ", end=" ")
                print(f"締め切り時間：{odds_info.deadline_time}, ", end=" ")
                if odds_info.odds_refresh_time == STATUS_DEADLINE: odds_refresh_time = "締切時"
                else: odds_refresh_time = odds_info.odds_refresh_time
                print(f"更新時間：{odds_refresh_time}, ", end=" ")
                print(f"賭け式：{COMBINATION_CHARACTERS[self.combination_type]}")
                self.odds_dict = json.loads(odds_info.odds_json)

                displayed_odds_count = 0
                for combination, odds in self.odds_dict[self.combination_type].items():
                    print(f"買い目：{Colorize.aqua_marine(combination)}, オッズ：{Colorize.salmon(odds, 5)}|", end=" ")
                    displayed_odds_count += 1
                    if displayed_odds_count == self.odds_per_line:
                        print("")
                        displayed_odds_count = 0
                break
        if not is_valid_enter:
            print(f"不正な入力です：{self.entered_field_code}")
            self.section = SECTION_CHOIE_RACE
            return False
        self.section = SECTION_CALCULATE_ODDS
        return True

    def section_calculate_odds(self):
        # 合成オッズ計算のための買い目を複数選択してもらう
        enter = input(
            "q:プログラムを終了する 0:レース選択に戻る 1:3連単オッズを表示する 2:3連複オッズを表示する\n"
            "合成オッズを計算するために買い目を空白区切りで入力してください：")
        if enter == "q":
            return False
        elif enter == "0":
            self.combination_type = TRIFECTA
            self.section = SECTION_CHOIE_RACE
            return True
        elif enter == "1":
            self.combination_type = TRIFECTA
            self.section = SECTION_DISPLAY_ODDS
            return True
        elif enter == "2":  
            self.combination_type = TRIO
            self.section = SECTION_DISPLAY_ODDS
            return True
        # 合成オッズを計算し出力する
        combinations = []
        for combination in enter.split(" "):
            if combination not in self.odds_dict[self.combination_type]:
                print(f"不正な入力です：{combination}")
                return True
            combinations.append(Combination(combination, self.odds_dict[self.combination_type][combination]))
        self.calc_composite_odds(betting_amount, combinations)
        return True
    
    def culc_betting_amount(self, total_betting_amount, composite_odds, odds, betting_selection):
        betting_amount = total_betting_amount * composite_odds / odds
        betting_amount = int(round(betting_amount / 100) * 100)
        estimated_refund_amount = int(betting_amount * odds)
        print(f"買い目：{betting_selection}, 賭け額：{betting_amount}円, 払い戻し額：{estimated_refund_amount}円")
        
        return betting_amount

    # 引数は買い目とオッズのペアのリスト、戻り値はなしで標準出力に結果を出力
    def calc_composite_odds(self, betting_amount, combinations):
        sum_odds = 0
        for combination in combinations:
            sum_odds += 1 / float(combination.odds)
        composite_odds = 1 / sum_odds
        print(f"合成オッズ：{composite_odds}")
        
        sum_betting_amount = 0
        for combination in combinations:
            odds = float(combination.odds)
            betting_selection = combination.combination
            allocated_betting_amount = self.culc_betting_amount(betting_amount, composite_odds, odds, betting_selection)
            sum_betting_amount += allocated_betting_amount
        print(f"合計賭け額:{sum_betting_amount}円")



if __name__ == "__main__":
    logging.info("composite_odds_calculator start.")

    parser = argparse.ArgumentParser(description='合成オッズ計算機')
    parser.add_argument("-b", type=int, default=10000, help="賭け額, default=10000")
    args = parser.parse_args()
    
    betting_amount = args.b
    ODDS_PER_LINE = int(os.environ['ODDS_PER_LINE'])

    # 別スレッドで1分おきにDBから最新のレース情報を取得する
    # 取得するのは当日各レース場の最新のレース情報だけ
    # 次のレースが締め切り10分前になるまでは直前の締め切られたレースの確定オッズで合成オッズを計算できる
    odds_info_manager = OddsInfoManager()
    odds_info_manager.start()

    cui_client = CUIClient(betting_amount, ODDS_PER_LINE)
    try:
        while True:
            if cui_client.get_section() == SECTION_CHOIE_RACE:
                # 最新のレース情報を表示(レース場、ラウンド)
                odds_infos = odds_info_manager.get_odds_infos()
                to_next_section = cui_client.section_choice_race(odds_infos)
                if not to_next_section: break

            if cui_client.get_section() == SECTION_DISPLAY_ODDS:
                # オッズ一覧表示（デフォルトは3連単）
                to_next_section = cui_client.section_display_odds()
                if not to_next_section: continue
                
            if cui_client.get_section() == SECTION_CALCULATE_ODDS:
                # 買い目の入力受付と合成オッズの計算
                is_continuation = cui_client.section_calculate_odds()
                if not is_continuation: break     
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected. Exiting gracefully.")
    except Exception as e:
        logging.error(e)
        print("予期せぬエラーが発生しました")

    odds_info_manager.stop()
    logging.info("composite_odds_calculator terminate.")

