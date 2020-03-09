import csv
import json
import datetime
import glob
import os
import urllib.request
from patients import PatientsReader

JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

class CovidDataManager:
    def __init__(self):
        self.data = {
            'contacts':{},
            'querents':{},
            'patients':{},
            'patients_summary':{},
            'discharges':{},
            'discharges_summary':{},
            'inspections':{},
            'inspections_summary':{},
            'better_patients_summary':{},
            'last_update':datetime.datetime.now(JST).isoformat(),
            'main_summary':{}
        }

    def fetch_data(self):
        pr = PatientsReader()
        self.data['patients'] = pr.make_patients_dict()
        self.data['patients_summary'] = pr.make_patients_summary_dict()

    def export_csv(self):
        for key in self.data:
            if key == 'last_update' or key == 'main_summary':
                continue

            datas = self.data[key]
            if datas == {}:
                continue
            
            maindatas = datas['data']
            header = list(maindatas[0].keys())
            csv_rows = [ header ]
            for d in maindatas:
                csv_rows.append( list(d.values()) )

            with open('data/' + key + '.csv', 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(csv_rows)

    def export_json(self, filepath='data/data.json'):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def export_json_from_name(self, key):
        with open('data/' + key + '.json', 'w', encoding='utf-8') as f:
            json.dump(self.data[key], f, indent=4, ensure_ascii=False)

    def import_csv(self):
        csvfiles = glob.glob('./import/*.csv')
        for csvfile in csvfiles:
            filename = os.path.splitext(os.path.basename(csvfile))[0]
            last_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(csvfile), JST).isoformat()
            datas = []
            with open(csvfile, encoding='utf-8') as f:
                rows = [row for row in csv.reader(f)]
                header = rows[0]
                maindatas = rows[1:]
                for d in maindatas:
                    data = {}
                    for i in range(len(header)):
                        data[header[i]] = d[i]
                        if header[i] == '小計':
                            data[header[i]] = int(d[i])
                    datas.append(data)

            self.data[filename] = {
                'data':datas,
                'date':last_modified_time
            }

    def import_csv_from_odp(self):
        responce = urllib.request.urlopen('https://www.harp.lg.jp/opendata/api/package_show?id=752c577e-0cbe-46e0-bebd-eb47b71b38bf')
        print(responce.getcode())
        if responce.getcode() == 200:
            loaded_json = json.loads(responce.read().decode('utf-8'))
            if loaded_json['success'] == True:
                resources = loaded_json['result']['resources']
                for resource in resources:
                    url = resource['download_url']
                    request_file = urllib.request.urlopen(url)
                    if request_file.getcode() == 200:
                        f = request_file.read().decode('utf-8')
                        filename = resource['filename'].rstrip('.csv')
                        last_modified_time = resource['updated']
                        datas = []
                        rows = [row for row in csv.reader(f.splitlines())]
                        header = rows[0]
                        maindatas = rows[1:]
                        for d in maindatas:
                            data = {}
                            for i in range(len(header)):
                                data[header[i]] = d[i]
                                if header[i] == '小計':
                                    data[header[i]] = int(d[i])
                            datas.append(data)

                        self.data[filename] = {
                            'data':datas,
                            'date':last_modified_time
                        }


if __name__ == "__main__":
    dm = CovidDataManager()
    dm.fetch_data()
    dm.import_csv()
    for key in dm.data:
        dm.export_json_from_name(key)