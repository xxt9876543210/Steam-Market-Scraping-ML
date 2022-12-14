import os
import requests
import time
import pandas as pd
from datetime import datetime, timedelta


def target_date_to_datetime(target_date, date_format="%Y-%m-%d"):
    target_datetime = datetime.strptime(target_date, date_format)
    return target_datetime


def datetime_to_timestamp(date_as_datetime):
    date_as_timestamp = int(datetime.timestamp(date_as_datetime))
    return date_as_timestamp


def get_steam_api_url(app_id):
    return f"https://store.steampowered.com/appreviews/{app_id}"


def get_request_params(target_timestamp):
    # References:
    # - https://partner.steamgames.com/doc/store/getreviews
    # - browser dev tools on store pages, e.g. https://store.steampowered.com/app/570/#app_reviews_hash

    if target_timestamp is None:
        raise Exception("Empty target_timestamp!")

    params = {
        "json": "1",
        "num_per_page": "0",  # text content of reviews is not needed
        # caveat: default seems to be "english", so reviews would be missing if unchanged!
        "language": "all",
        # caveat: default is "steam", so reviews would be missing if unchanged!
        "purchase_type": "all",
        # to un-filter review-bombs, e.g. https://store.steampowered.com/app/481510/
        "filter_offtopic_activity": "0",
        "start_date": "1",  # this is the minimal value which allows to filter by date
        "end_date": str(target_timestamp),
        "date_range_type": "include",  # this parameter is needed to filter by date
    }

    return params


def download_review_stats(app_id, target_timestamp):
    url = get_steam_api_url(app_id)
    params = get_request_params(target_timestamp)
    response = requests.get(url, params=params)

    if response.ok:
        result = response.json()
    else:
        result = None

    return result


def get_info(res):
    fields = ['total_reviews', 'total_positive',
              'total_negative', 'review_score']
    query_summary = res["query_summary"]
    info = dict()
    for key in fields:
        info[key] = query_summary[key]

    return info


def download_review_to_df(input_path, file_name):
    df = pd.read_csv(input_path+file_name)
    app_id = file_name.split(".")[0]
    data = dict()
    for target_date in df["date"]:
        target_datetime = target_date_to_datetime(target_date)
        target_timestamp = datetime_to_timestamp(target_datetime)
        res = download_review_stats(app_id, target_timestamp)
        if not res:
            print(f"Invalid appid {app_id} OR Rate Limit !!!")
            print(data)
            return
        info = get_info(res)
        data[target_date] = info
        # print(target_date, info)
        time.sleep(1)
    review_df = pd.DataFrame.from_dict(
        data, orient='index').reset_index(drop=True)
    return pd.concat([df, review_df], axis=1)


if __name__ == "__main__":

    input_path = "../../analysis/priceChange/data/"
    output_path = "./data/price_change_review/"
    os.makedirs(output_path, exist_ok=True)
    input_list = os.listdir(input_path)

    finished = []
    if os.path.exists("./finished.txt"):
        with open("./finished.txt", 'r', encoding="utf-8") as f:
            finished = f.read().splitlines()
        input_list = list(set(input_list) - set(finished))

    count = 0
    while input_list:
        file_name = input_list.pop()
        print("downloading", file_name, "...")
        df = download_review_to_df(input_path, file_name)
        if type(df) != type(None):
            df.to_csv(output_path+file_name, encoding="utf-8", index=False)
            finished.append(file_name)
        # time.sleep(5)
        count += 1
        if count % 15 == 0:
            print(f"#queries {count} reached. Cooldown: {(2 * 60) + 8} s")
            time.sleep((2 * 60) + 8)
        with open("./finished.txt", "w", encoding="utf-8") as f:
            for name in finished:
                f.write(name+"\n")
    