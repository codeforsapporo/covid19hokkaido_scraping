import csv
import json
import datetime
import glob
import os
import urllib.request
import jsonschema

# ignore ssl verify
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

#日本標準時
JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

#設定ファイル
import settings
REMOTE_SOURCES = settings.REMOTE_SOURCES #外部ファイルの参照設定
HEADER_TRANSLATIONS = settings.HEADER_TRANSLATIONS #headerの変換一覧
INT_CAST_KEYS = settings.INT_CAST_KEYS #intにキャストすべきkey
CODECS = settings.CODECS #ファイルエンコーディングリスト

#バリデーション用のスキーマ定義
import schemas
SCHEMAS = schemas.SCHEMAS

class CovidDataManager:
    def __init__(self):
        self.data = {
            'last_update':datetime.datetime.now(JST).isoformat(), 
        }
    
    #REMOTE_SOURCESに基づき外部ファイルにアクセス・データ取得
    def fetch_datas(self):
        for key in REMOTE_SOURCES:
            self.fetch_data_of(key)

    def fetch_data_of(self, key):
        print(key)
        datatype = REMOTE_SOURCES[key]['type']
        dataurl = REMOTE_SOURCES[key]['url']
        data = {}
        if datatype == 'odp':
            data = self.import_odp_csv(key, dataurl)
        elif datatype == 'csv':
            data = self.import_csv_from(dataurl)
        
        self.data[key] = data

    def export_csv_of(self, key):
        maindatas = datas['data']
        header = list(maindatas[0].keys())
        csv_rows = [ header ]
        for d in maindatas:
            csv_rows.append( list(d.values()) )

        with open('data/' + key + '.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows)

    def export_csvs(self):
        for key in self.data:
            self.export_csv_of(key)

    def export_json_of(self, key, directory='data/'):
        with open(directory + key + '.json', 'w', encoding='utf-8') as f:
            json.dump(self.data[key], f, indent=4, ensure_ascii=False)

    def export_jsons(self, directory='data/'):
        for key in self.data:
            print(key + '.json')
            self.export_json_of(key, directory)

    #CSV文字列を[dict]型に変換
    def csvstr_to_dicts(self, csvstr)->list:
        datas = []
        rows = [row for row in csv.reader(csvstr.splitlines())]
        header = rows[0]
        header = self.translate_header(header)
        maindatas = rows[1:]
        for d in maindatas:
            #空行はスキップ
            if d == []:
                continue
            data = {}
            for i in range(len(header)):
                data[header[i]] = d[i]
                if header[i] in INT_CAST_KEYS:
                    data[header[i]] = int(d[i])
            datas.append(data)
        return datas

    #生成されるjsonの正当性チェック
    def validate(self):
        for key in self.data:
            jsonschema.validate(self.data[key], SCHEMAS[key])

    #HEADER_TRANSLATIONSに基づきデータのヘッダ(key)を変換
    def translate_header(self, header:list)->list:
        for i in range(len(header)):
            for key in HEADER_TRANSLATIONS:
                if header[i] == key:
                    header[i] = HEADER_TRANSLATIONS[key]
        return header

    #デコード出来るまでCODECS内全コーデックでトライする
    def decode_csv(self, csv_data)->str:
        print('csv decoding')
        for codec in CODECS:
            try:
                csv_str = csv_data.decode(codec)
                print('ok:' + codec)
                return csv_str
            except:
                print('ng:' + codec)
                continue
        print('Appropriate codec is not found.')


    #importフォルダ内のCSVを全て読み込む
    def import_local_csvs(self):
        csvfiles = glob.glob('./import/*.csv')
        for csvfile in csvfiles:
            filename = os.path.splitext(os.path.basename(csvfile))[0]
            last_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(csvfile), JST).isoformat()
            datas = []

            with open(csvfile, encoding='utf-8') as f:
                datas = self.csvstr_to_dicts(f.read())

            self.data[filename] = {
                'data':datas,
                'last_update':last_modified_time
            }

    #Open Data Potal API経由でCSVファイルをインポート
    def import_odp_csv(self, key, odp_url):
        response = urllib.request.urlopen(odp_url)

        status_code = response.getcode()
        if not status_code == 200:
            print(status_code, 'error occured')
            return

        loaded_json = json.loads(response.read().decode('utf-8'))
        if not loaded_json['success']:
            print('get json error')
            return

        url = ''
        updated_datetime = ''
        resources = loaded_json['result']['resources']
        for resource in resources:
            if resource['name'] == key + '.csv':
                url = resource['download_url']
                updated_datetime = resource['updated'] #iso-8601

        request_file = urllib.request.urlopen(url)
        if not request_file.getcode() == 200:
            print('csv get error')
            return
        
        csvstr = self.decode_csv(request_file.read())
        datas = self.csvstr_to_dicts(csvstr)

        return {
            'data':datas,
            'last_update':updated_datetime
        }

    #外部のCSVファイルをインポート url=xxxx/xxxx.csv
    def import_csv_from(self, csvurl):
        request_file = urllib.request.urlopen(csvurl)
        if not request_file.getcode() == 200:
            return
        
        f = self.decode_csv(request_file.read())
        filename = os.path.splitext(os.path.basename(csvurl))[0]
        datas = self.csvstr_to_dicts(f)

        return {
            'data': datas,
            'last_update': datetime.datetime.now(JST).isoformat()
        }

if __name__ == "__main__":
    dm = CovidDataManager()
    print('---fetch data---')
    #REMOTE_SOUCESのすべてのソースにアクセス・データ取得しself.dataに保存
    dm.fetch_datas()
    print('---done---')
    #importフォルダ内のCSVをすべて読み込んでself.dataに保存
    dm.import_local_csvs()
    print('---export jsons---')
    #dict型であるself.dataの全要素がスキーマ定義に適合するかチェック
    dm.validate()
    #self.dataの全要素をjson形式で出力
    dm.export_jsons()
    print('---done---')