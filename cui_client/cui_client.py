import json
import argparse
import logging
from odds_info_manager import OddsInfoManager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="composite_odds_calculator.log",
    filemode="a"  # "a"は追記モード, "w"にすると上書きモード
)

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

    
class Combination:
    def __init__(self, combination, odds):
        self.combination = combination
        self.odds = odds


def culc_betting_amount(total_betting_amount, composite_odds, odds, betting_selection):
    betting_amount = total_betting_amount * composite_odds / odds
    betting_amount = int(round(betting_amount / 100) * 100)
    estimated_refund_amount = int(betting_amount * odds)
    print(f"買い目：{betting_selection}, 賭け額：{betting_amount}円, 払い戻し額：{estimated_refund_amount}円")
    
    return betting_amount

# 引数は買い目とオッズのペアのリスト、戻り値はなしで標準出力に結果を出力
def calc_composite_odds(betting_amount, combinations):
    sum_odds = 0
    for combination in combinations:
        sum_odds += 1 / float(combination.odds)
    composite_odds = 1 / sum_odds
    print(f"合成オッズ：{composite_odds}")
    
    sum_betting_amount = 0
    for combination in combinations:
        odds = float(combination.odds)
        betting_selection = combination.combination
        allocated_betting_amount = culc_betting_amount(betting_amount, composite_odds, odds, betting_selection)
        sum_betting_amount += allocated_betting_amount

    print(f"合計賭け額:{sum_betting_amount}円")



if __name__ == "__main__":
    logging.info("composite_odds_calculator start.")

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
    odds_dict = None
    section = 0
    try:
        while True:
            if section == 0:
                section = 1
                # 最新のレース情報を表示(レース場、ラウンド)
                odds_infos = odds_info_manager.get_odds_infos()
                for odds_info in odds_infos:
                    print(f"ID：{odds_info.field_code}, レース場：{FIELD_CODE_MAP[odds_info.field_code]}, レース：{odds_info.race_number}, 締め切り時間：{odds_info.deadline_time}")
                # 買い目毎のオッズを出力するためにどのレースのオッズを見るか選択してもらう
                enter = input("q:プログラムを終了する\nIDを入力してください：")
                if enter == "q": break
                # オッズ一覧表示
                for odds_info in odds_infos:
                    if odds_info.field_code == enter:
                        print(f"レース場：{FIELD_CODE_MAP[odds_info.field_code]}, レース：{odds_info.race_number}, 締め切り時間：{odds_info.deadline_time}")
                        odds_dict = json.loads(odds_info.odds_json)
                        for combination, odds in odds_dict.items():
                            print(f"買い目：{combination}, オッズ：{odds}")
                        break
            if section == 1:
                # 合成オッズ計算のための買い目を複数選択してもらう
                enter = input(
                    "q:プログラムを終了する 0:レース選択に戻る\n"
                    "合成オッズを計算するために買い目を空白区切りで入力してください：")
                logging.info(f"enter:{enter}")
                if enter == "q":
                    break
                elif enter == "0":
                    section = 0
                    continue
                # 合成オッズを計算し出力する
                combinations = []
                for combination in enter.split(" "):
                    combinations.append(Combination(combination, odds_dict[combination]))
                calc_composite_odds(betting_amount, combinations)   

    except Exception as e:
        logging.error(e)
        print("予期せぬエラーが発生しました")
    odds_info_manager.stop()
    logging.info("composite_odds_calculator terminate.")

